"""Small async client for the Eetlijst (v5) GraphQL API."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import json
from typing import Any

import aiohttp

API_URL = "https://api.eetlijst.nl/v1/graphql"
TIMEOUT = aiohttp.ClientTimeout(total=30)

AUTH_ERROR_CODES = {"invalid-jwt", "access-denied", "invalid-headers", "jwt-invalid"}


class EetlijstError(Exception):
    """Generic API error."""


class EetlijstAuthError(EetlijstError):
    """Token is invalid or expired."""


class EetlijstConnectionError(EetlijstError):
    """Could not reach the API."""


def clean_token(token: str) -> str:
    """Strip whitespace, quotes and a 'Bearer ' prefix from a pasted token."""
    token = token.strip().strip('"').strip("'").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode the JWT payload without verifying it (we only need sub/exp)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload).decode())
    except (ValueError, UnicodeDecodeError):
        return {}


ATTENDANCE_FIELDS = """
fragment AttendanceFields on eetschema_event_attendees {
  status
  number_guests
  comment
  user_in_group { user { id name } }
}
"""

Q_GROUPS = """
query Groups {
  eetschema_group { id name }
}
"""

Q_MEMBERS = """
query Members($groupId: uuid!) {
  eetschema_group_by_pk(id: $groupId) {
    id
    name
    users_in_groups(where: {active: {_eq: true}}, order_by: {order: asc}) {
      order
      user { id name }
    }
  }
}
"""

Q_POPULATE = """
query AutomaticEvents($groupId: uuid!, $date: String!) {
  queryTodaysEvents(group_id: $groupId, date: $date) { id }
}
"""

Q_EVENTS = (
    """
query Events($groupId: uuid!, $from: timestamptz!, $to: timestamptz!) {
  eetschema_event(
    where: {group_id: {_eq: $groupId}, start_date: {_gte: $from, _lt: $to}}
    order_by: {start_date: asc}
  ) {
    id
    name
    open
    start_date
    signup_deadline
    user { id name }
    event_attendees { ...AttendanceFields }
  }
}
"""
    + ATTENDANCE_FIELDS
)

M_UPDATE_ATTENDANCE = (
    """
mutation UpdateAttendance($eventId: uuid!, $userId: String!, $_set: eetschema_event_attendees_set_input!) {
  update_eetschema_event_attendees_by_pk(
    pk_columns: {event_id: $eventId, user_id: $userId}
    _set: $_set
  ) { ...AttendanceFields }
}
"""
    + ATTENDANCE_FIELDS
)

M_INSERT_ATTENDANCE = (
    """
mutation UpdateManyAttendance($updates: [eetschema_event_attendees_insert_input!]!) {
  insert_eetschema_event_attendees(
    objects: $updates
    on_conflict: {constraint: event_attending_members_pkey, update_columns: [status, number_guests, user_changed_status, comment]}
  ) { returning { ...AttendanceFields } }
}
"""
    + ATTENDANCE_FIELDS
)

LIST_FIELDS = "id text checked active created_at updated_at"

Q_LIST = f"""
query ListItems($groupId: uuid!) {{
  open: eetschema_list(
    where: {{group_id: {{_eq: $groupId}}, active: {{_eq: true}}, checked: {{_eq: false}}}}
    order_by: {{created_at: asc}}
  ) {{ {LIST_FIELDS} }}
  done: eetschema_list(
    where: {{group_id: {{_eq: $groupId}}, active: {{_eq: true}}, checked: {{_eq: true}}}}
    order_by: {{updated_at: desc}}
    limit: 15
  ) {{ {LIST_FIELDS} }}
}}
"""

M_CREATE_LIST_ITEM = f"""
mutation CreateListItem($groupId: uuid!, $text: String!) {{
  insert_eetschema_list_one(
    object: {{group_id: $groupId, text: $text, active: true, checked: false}}
  ) {{ {LIST_FIELDS} }}
}}
"""

M_UPDATE_LIST_ITEM = f"""
mutation UpdateListItem($id: uuid!, $_set: eetschema_list_set_input!) {{
  update_eetschema_list_by_pk(pk_columns: {{id: $id}}, _set: $_set) {{ {LIST_FIELDS} }}
}}
"""


class EetlijstApi:
    """Thin GraphQL wrapper."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._session = session
        self.token = clean_token(token)
        self.claims = decode_jwt(self.token)

    @property
    def user_id(self) -> str | None:
        """User id from the token."""
        return self.claims.get("sub")

    @property
    def user_name(self) -> str | None:
        """User name from the token."""
        return self.claims.get("name")

    @property
    def expires(self) -> datetime | None:
        """Token expiry."""
        exp = self.claims.get("exp")
        if exp is None:
            return None
        return datetime.fromtimestamp(exp, tz=UTC)

    async def request(self, query: str, variables: dict[str, Any] | None = None) -> dict:
        """Run a GraphQL request and return its data."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        try:
            async with self._session.post(
                API_URL,
                json={"query": query, "variables": variables or {}},
                headers=headers,
                timeout=TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise EetlijstAuthError(f"HTTP {resp.status}")
                try:
                    body = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise EetlijstConnectionError(
                        f"Ongeldig antwoord (HTTP {resp.status})"
                    ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise EetlijstConnectionError(str(err) or type(err).__name__) from err

        if not isinstance(body, dict):
            raise EetlijstConnectionError("Ongeldig antwoord van Eetlijst")

        if errors := body.get("errors"):
            messages = []
            for error in errors:
                code = (error.get("extensions") or {}).get("code", "")
                message = error.get("message", "")
                if code in AUTH_ERROR_CODES or "jwt" in message.lower():
                    raise EetlijstAuthError(message or code)
                messages.append(message or code)
            raise EetlijstError("; ".join(messages))

        if resp.status >= 400:
            raise EetlijstConnectionError(f"HTTP {resp.status}")
        return body.get("data") or {}

    # ---- groups / members ----------------------------------------------
    async def get_groups(self) -> list[dict]:
        """Groups the user can see."""
        data = await self.request(Q_GROUPS)
        return data.get("eetschema_group") or []

    async def get_group(self, group_id: str) -> dict | None:
        """Group with its active members."""
        data = await self.request(Q_MEMBERS, {"groupId": group_id})
        return data.get("eetschema_group_by_pk")

    # ---- events --------------------------------------------------------
    async def populate_dinners(self, group_id: str, when: datetime) -> list[str]:
        """Make sure the dinner for a day exists; returns event ids."""
        data = await self.request(
            Q_POPULATE,
            {"groupId": group_id, "date": when.strftime("%Y-%m-%d:%H:%M:%S")},
        )
        result = data.get("queryTodaysEvents")
        if isinstance(result, dict):
            result = [result]
        return [e["id"] for e in result or [] if isinstance(e, dict) and e.get("id")]

    async def get_events(self, group_id: str, start: datetime, end: datetime) -> list[dict]:
        """Events (with attendees) between start and end."""
        data = await self.request(
            Q_EVENTS,
            {"groupId": group_id, "from": start.isoformat(), "to": end.isoformat()},
        )
        return data.get("eetschema_event") or []

    async def set_attendance(
        self,
        event_id: str,
        user_id: str,
        *,
        status: str | None = None,
        guests: int | None = None,
        comment: str | None = None,
        clear_comment: bool = False,
    ) -> dict:
        """Update (or create) a user's attendance for an event."""
        changes: dict[str, Any] = {}
        if status is not None:
            changes["status"] = status
            changes["user_changed_status"] = True
        if guests is not None:
            changes["number_guests"] = guests
        if comment is not None or clear_comment:
            changes["comment"] = comment or None
        if not changes:
            raise ValueError("Niets om te wijzigen")

        data = await self.request(
            M_UPDATE_ATTENDANCE,
            {"eventId": event_id, "userId": user_id, "_set": changes},
        )
        if row := data.get("update_eetschema_event_attendees_by_pk"):
            return row

        # No row yet for this user/event: insert one.
        insert = {
            "event_id": event_id,
            "user_id": user_id,
            "status": status or "dont_know_yet",
            "number_guests": guests or 0,
            "user_changed_status": status is not None,
        }
        if comment:
            insert["comment"] = comment
        data = await self.request(M_INSERT_ATTENDANCE, {"updates": [insert]})
        rows = (data.get("insert_eetschema_event_attendees") or {}).get("returning") or []
        if not rows:
            raise EetlijstError("Inschrijving is niet opgeslagen (is de lijst gesloten?)")
        return rows[0]

    # ---- shopping list -------------------------------------------------
    async def get_list(self, group_id: str) -> list[dict]:
        """Open items plus the most recently checked ones."""
        data = await self.request(Q_LIST, {"groupId": group_id})
        return (data.get("open") or []) + (data.get("done") or [])

    async def add_list_item(self, group_id: str, text: str) -> dict:
        """Add an item."""
        data = await self.request(M_CREATE_LIST_ITEM, {"groupId": group_id, "text": text})
        return data.get("insert_eetschema_list_one") or {}

    async def update_list_item(self, item_id: str, changes: dict[str, Any]) -> dict:
        """Change an item (text / checked / active)."""
        data = await self.request(M_UPDATE_LIST_ITEM, {"id": item_id, "_set": changes})
        return data.get("update_eetschema_list_by_pk") or {}
