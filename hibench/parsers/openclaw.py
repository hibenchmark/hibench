from __future__ import annotations

from .available_skills import AvailableSkillsXmlMixin
from .base import ChatRoleParser


class OpenClawParser(AvailableSkillsXmlMixin, ChatRoleParser):
    parser_id = "openclaw"
    require_immediate_skill = True
