#!/usr/bin/env python3
"""Helpers for fetching and normalizing NHS service-search data."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

RAW_RESPONSE_PATH = Path("data/raw/nhs_service_search.json")
NORMALIZED_PATH = Path("data/raw/nhs_practices_normalized.json")

BOOL_TRUE = {"yes", "true", "1", "y"}
BOOL_FALSE = {"no", "false", "0", "n"}


def _extract_result_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("value", "results", "items", "entry", "@graph"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [x for x in candidate if isinstance(x, dict)]

    return []


def _iter_string_values(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_iter_string_values(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_iter_string_values(v))
    return out


def _pick(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _normalize_postcode(postcode: str) -> str:
    return re.sub(r"\s+", "", postcode.strip().upper())


def _looks_like_dental(record: dict[str, Any]) -> bool:
    org_type_id = _pick(record, "OrganisationTypeId", "organisationTypeId")
    if isinstance(org_type_id, str) and org_type_id.strip().upper() == "DEN":
        return True
    org_type = _pick(record, "OrganisationType", "organisationType")
    if isinstance(org_type, str) and "dent" in org_type.lower():
        return True
    text_blob = " ".join(_iter_string_values(record)).lower()
    return "dent" in text_blob


def _normalize_yes_no_unknown(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "unknown"
    text = str(value).strip().lower()
    if text in BOOL_TRUE:
        return "yes"
    if text in BOOL_FALSE:
        return "no"
    if "yes" in text:
        return "yes"
    if "no" in text:
        return "no"
    return "unknown"


def _availability_from_record(record: dict[str, Any]) -> tuple[str, str]:
    accepting = record.get("AcceptingPatients")
    if isinstance(accepting, dict):
        dentist_list = accepting.get("Dentist")
        if isinstance(dentist_list, list) and dentist_list:
            adults = "unknown"
            children = "unknown"
            for item in dentist_list:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("Name", "")).lower()
                accepted = _normalize_yes_no_unknown(item.get("AcceptingPatients"))
                if "adult" in name and adults == "unknown":
                    adults = accepted
                if "children" in name and children == "unknown":
                    children = accepted
            if adults != "unknown" or children != "unknown":
                return adults, children

    adults = _normalize_yes_no_unknown(
        _pick(
            record,
            "accepting_adults",
            "acceptingAdults",
            "AcceptingAdults",
            "accepting_new_adult_patients",
            "acceptingAdultNhsPatients",
            "AcceptingNewNHSAdultPatients",
        )
    )
    children = _normalize_yes_no_unknown(
        _pick(
            record,
            "accepting_children",
            "acceptingChildren",
            "AcceptingChildren",
            "accepting_new_child_patients",
            "acceptingChildNhsPatients",
            "AcceptingNewNHSChildPatients",
        )
    )

    if adults != "unknown" or children != "unknown":
        return adults, children

    text_blob = " ".join(_iter_string_values(record)).lower()

    adult_match = re.search(r"adult[^.\n]{0,40}\b(yes|no)\b", text_blob)
    child_match = re.search(r"child[^.\n]{0,40}\b(yes|no)\b", text_blob)

    if adult_match:
        adults = "yes" if adult_match.group(1) == "yes" else "no"
    if child_match:
        children = "yes" if child_match.group(1) == "yes" else "no"

    return adults, children


def _extract_address(record: dict[str, Any]) -> tuple[str, str]:
    postcode = _pick(record, "postcode", "Postcode", "postalCode", "PostalCode")
    if isinstance(postcode, dict):
        postcode = _pick(postcode, "value", "postcode", "Postcode")

    address_candidate = _pick(record, "address", "Address")
    if isinstance(address_candidate, dict):
        parts = [
            str(_pick(address_candidate, "line1", "Line1", "addressLine1", "AddressLine1") or "").strip(),
            str(_pick(address_candidate, "line2", "Line2", "addressLine2", "AddressLine2") or "").strip(),
            str(_pick(address_candidate, "city", "City", "town", "Town") or "").strip(),
        ]
        if not postcode:
            postcode = _pick(address_candidate, "postcode", "Postcode", "postalCode", "PostalCode")
        address = ", ".join([p for p in parts if p])
    else:
        parts = [
            str(_pick(record, "Address1", "address1") or "").strip(),
            str(_pick(record, "Address2", "address2") or "").strip(),
            str(_pick(record, "Address3", "address3") or "").strip(),
            str(_pick(record, "City", "city", "Town", "town") or "").strip(),
        ]
        address = ", ".join([p for p in parts if p])

    if not isinstance(postcode, str):
        postcode = ""

    return address, postcode.strip().upper()


def normalize_nhs_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []

    for record in records:
        if not _looks_like_dental(record):
            continue

        name = _pick(record, "practice_name", "name", "Name", "OrganisationName", "organisationName")
        if not isinstance(name, str) or not name.strip():
            continue

        practice_id = _pick(
            record,
            "practice_id",
            "id",
            "ID",
            "OrganisationID",
            "organisationID",
            "ODSCode",
            "odsCode",
        )
        if not isinstance(practice_id, str) or not practice_id.strip():
            digest = hashlib.sha1(name.strip().lower().encode("utf-8")).hexdigest()[:12]
            practice_id = f"NHS-{digest}"

        address, postcode = _extract_address(record)
        if not postcode:
            continue

        adults, children = _availability_from_record(record)
        latitude = _pick(record, "Latitude", "latitude")
        longitude = _pick(record, "Longitude", "longitude")
        county = _pick(record, "County", "county")

        lat_text = ""
        lon_text = ""
        try:
            if latitude is not None and longitude is not None:
                lat_text = str(float(latitude))
                lon_text = str(float(longitude))
        except (TypeError, ValueError):
            lat_text = ""
            lon_text = ""

        area_code = ""
        if isinstance(county, str) and county.strip():
            area_code = f"COUNTY::{county.strip().upper()}"

        normalized.append(
            {
                "practice_id": practice_id.strip(),
                "practice_name": name.strip(),
                "address": address,
                "postcode": postcode,
                "postcode_norm": _normalize_postcode(postcode),
                "lat": str(_pick(record, "Latitude", "latitude") or ""),
                "lon": str(_pick(record, "Longitude", "longitude") or ""),
                "area_code": str(_pick(record, "LSOA", "lsoa") or ""),
                "accepting_adults": adults,
                "accepting_children": children,
                "last_reported": date.today().isoformat(),
                "lat": lat_text,
                "lon": lon_text,
                "area_code": area_code,
            }
        )

    dedup: dict[tuple[str, str], dict[str, str]] = {}
    for row in normalized:
        key = (row["practice_name"].lower(), row["postcode_norm"])
        dedup[key] = row

    return list(dedup.values())


def fetch_nhs_service_search_pages() -> list[dict[str, Any]]:
    subscription_key = os.getenv("NHS_API_SUBSCRIPTION_KEY", "").strip() or os.getenv(
        "NHS_API_SUBSCRIPTION_SECRET", ""
    ).strip()
    if not subscription_key:
        raise RuntimeError("NHS_API_SUBSCRIPTION_KEY is not set")

    base_url = os.getenv(
        "NHS_SERVICE_SEARCH_URL", "https://int.api.service.nhs.uk/service-search-api"
    )
    search = os.getenv("NHS_SERVICE_SEARCH_QUERY", "dentist")
    api_version = os.getenv("NHS_SERVICE_SEARCH_API_VERSION", "3").strip() or "3"
    page_size = int(os.getenv("NHS_SERVICE_SEARCH_PAGE_SIZE", "200"))
    max_pages = int(os.getenv("NHS_SERVICE_SEARCH_MAX_PAGES", "80"))

    all_items: list[dict[str, Any]] = []

    for page in range(max_pages):
        skip = page * page_size
        params = urlencode(
            {
                "api-version": api_version,
                "search": search,
                "$skip": skip,
                "$top": page_size,
                "$count": "true",
            }
        )
        url = f"{base_url}?{params}"

        request = Request(
            url,
            headers={
                "apikey": subscription_key,
                "accept": "application/json",
                "User-Agent": "dental-deserts-data-pipeline/1.0",
            },
        )

        try:
            with urlopen(request, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="ignore")[:500]
            except Exception:
                body = ""
            safe_url = url.split("?", 1)[0]
            raise RuntimeError(
                f"NHS API HTTP {exc.code} for {safe_url} (api-version={api_version}). "
                "Check API product access and key. "
                f"Body: {body}"
            ) from exc

        items = _extract_result_items(payload)
        if not items:
            break

        all_items.extend(items)

        if len(items) < page_size:
            break

    RAW_RESPONSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_RESPONSE_PATH.write_text(
        json.dumps({"retrieved": date.today().isoformat(), "items": all_items}, separators=(",", ":")),
        encoding="utf-8",
    )

    return all_items


def write_normalized_snapshot(rows: list[dict[str, str]]) -> None:
    NORMALIZED_PATH.parent.mkdir(parents=True, exist_ok=True)
    NORMALIZED_PATH.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")


def read_normalized_snapshot() -> list[dict[str, str]]:
    if not NORMALIZED_PATH.exists():
        return []
    content = json.loads(NORMALIZED_PATH.read_text(encoding="utf-8"))
    return [x for x in content if isinstance(x, dict)]
