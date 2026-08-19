class TestTheInstructionMatchesReality:
    """The agent is told what tools it has. That list is prose, and prose does
    not fail to compile when a tool is removed.

    Five tools were consolidated away and the instruction went on describing all
    nine for a while: the agent was being told it could call `recall`,
    `note_preference` and `what_do_you_remember`, none of which existed. An
    agent that believes it has a capability it does not have is the same class
    of failure as a tool that reports doing something it did not do, which this
    project has now hit four times.
    """

    def _named_tools(self) -> set[str]:
        import re

        from sampan.companion import BASE_INSTRUCTION

        block = BASE_INSTRUCTION.split("The tools you have")[1]
        block = block.split("Tool results carry")[0]
        return set(re.findall(r"^- (\w+) —", block, re.M))

    def _real_tools(self) -> set[str]:
        from sampan.tools import CallMemory, build_tools

        return {t.__name__ for t in build_tools(CallMemory())}

    def test_every_tool_it_is_told_about_exists(self) -> None:
        invented = self._named_tools() - self._real_tools()

        assert not invented, f"instruction promises tools that do not exist: {invented}"

    def test_every_tool_it_has_is_explained(self) -> None:
        """A tool the agent is never told about is one it will not reach for."""
        unexplained = self._real_tools() - self._named_tools()

        assert not unexplained, f"tools nobody told the agent about: {unexplained}"
