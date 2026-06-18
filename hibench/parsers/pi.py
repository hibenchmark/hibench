from __future__ import annotations

from .available_skills import AvailableSkillsXmlMixin
from .base import ChatRoleParser


class PiParser(AvailableSkillsXmlMixin, ChatRoleParser):
    parser_id = "pi"
