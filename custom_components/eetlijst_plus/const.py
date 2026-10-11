"""Constants for Eetlijst+."""

from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "eetlijst_plus"
LOGGER = logging.getLogger(__package__)

CONF_GROUP_ID = "group_id"
CONF_GROUP_NAME = "group_name"

UPDATE_INTERVAL = timedelta(minutes=2)
DAYS_AHEAD = 7

STATUS_COOK = "cook"
STATUS_EAT = "eat_only"
STATUS_GROCERIES = "got_groceries"
STATUS_NOT = "not_attending"
STATUS_UNKNOWN = "dont_know_yet"
STATUS_NONE = "no_status"

# Statuses a user can pick (in display order).
SETTABLE_STATUSES = [
    STATUS_EAT,
    STATUS_COOK,
    STATUS_GROCERIES,
    STATUS_NOT,
    STATUS_UNKNOWN,
]
# Statuses that mean "I'm eating along".
EATING_STATUSES = {STATUS_COOK, STATUS_EAT, STATUS_GROCERIES}
# All states a person sensor can have.
ALL_STATES = [*SETTABLE_STATUSES, STATUS_NONE]

SERVICE_SET_STATUS = "set_status"
ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_DATE = "date"
ATTR_STATUS = "status"
ATTR_GUESTS = "guests"
ATTR_COMMENT = "comment"
