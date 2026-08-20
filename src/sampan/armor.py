"""Screening the transcript before any of it reaches the database.

    Transcript ──> Model Armor ──> de-identified text ──> save_conversation
                                                     └──> extraction, facts

One screen, before the first write, and the *screened* text is what everything
downstream sees. That last part is not a detail. `build_facts` refuses a fact
whose quote is not present in the transcript, so extracting from the original
while storing the redacted version would silently start refusing facts whose
quotes contain a redaction — the archive would lose exactly the sentences that
had something in them worth protecting.

The tension this sits in, stated plainly because it cannot be designed away:
the product's promise is that her words are the artefact, kept verbatim (O3),
and this deliberately alters them. That is the right trade only for identifiers
nobody wants in a database — an account number, an IC, a phone number — and it
would be the wrong trade for anything that carries meaning. Model Armor's SDP
filter is what draws that line, not this module.

Fail closed. If screening cannot run, the transcript is not stored. That loses
a call, which is serious and is the point: a security control that degrades to
"store it anyway" is not a control. It matches the posture the service already
takes on a missing project or a missing key (D2).
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings


class Finding(BaseModel):
    """One thing the screen objected to."""

    filter: str = Field(description="sdp | rai | prompt_injection | malicious_uri")
    detail: str = ""


class Screened(BaseModel):
    """The result of screening one transcript.

    `stored` is the whole question: false means nothing goes in the database,
    and the caller must not write the text anyway.
    """

    text: str = ""
    findings: list[Finding] = Field(default_factory=list)
    stored: bool = True
    reason: str = ""

    @property
    def redacted(self) -> bool:
        return any(f.filter == "sdp" for f in self.findings)


class Screen(Protocol):
    """Model Armor, behind a seam. Everything downstream of screening is
    exercisable without a network by passing a fake."""

    def sanitize(self, text: str) -> Screened: ...


class AllowAll:
    """No screening configured. Used when no template is set, and in tests
    that are about something else."""

    def sanitize(self, text: str) -> Screened:
        return Screened(text=text, stored=True)


class ModelArmorScreen:
    """The real thing: one `sanitizeUserPrompt` call against a template.

    The template carries the policy — which info types to de-identify, which
    responsible-AI categories to block — because that is a decision for whoever
    runs the deployment and not one to hard-code here.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def sanitize(self, text: str) -> Screened:
        from google.api_core.client_options import ClientOptions
        from google.cloud import modelarmor_v1 as ma

        location = self._settings.armor_location
        client = ma.ModelArmorClient(
            client_options=ClientOptions(
                api_endpoint=f"modelarmor.{location}.rep.googleapis.com"
            )
        )
        template = (
            f"projects/{self._settings.project_id}/locations/{location}"
            f"/templates/{self._settings.armor_template}"
        )
        response = client.sanitize_user_prompt(
            request=ma.SanitizeUserPromptRequest(
                name=template,
                user_prompt_data=ma.DataItem(text=text),
            )
        )
        return _read(response.sanitization_result, text)


def _read(result: Any, original: str) -> Screened:
    """Turn Model Armor's result into the two things the caller needs: the text
    to store, and why it is or is not the text that came in."""
    from google.cloud import modelarmor_v1 as ma

    findings: list[Finding] = []
    text = original

    for name, filter_result in (result.filter_results or {}).items():
        sdp = getattr(filter_result, "sdp_filter_result", None)
        deidentified = getattr(sdp, "deidentify_result", None) if sdp else None
        if deidentified and getattr(deidentified, "data", None):
            # The whole reason for the screen: identifiers replaced, and the
            # replacement is what gets stored and extracted from.
            replacement = getattr(deidentified.data, "text", "")
            if replacement:
                text = replacement
            findings.append(
                Finding(
                    filter="sdp",
                    detail=", ".join(
                        i.name for i in getattr(deidentified, "info_types", []) or []
                    ),
                )
            )
            continue
        matched = getattr(filter_result, "match_state", None)
        if matched == ma.FilterMatchState.MATCH_FOUND:
            findings.append(Finding(filter=str(name)))

    return Screened(text=text, findings=findings, stored=True)


def screen(text: str, screener: Screen | None) -> Screened:
    """Screen a transcript, or refuse to store it.

    Never raises. A screening failure returns `stored=False`, which is the
    fail-closed path: the caller writes nothing rather than writing text that
    was never checked.
    """
    if screener is None:
        return Screened(text=text, stored=True)
    try:
        return screener.sanitize(text)
    except Exception as error:  # noqa: BLE001 -- see the module docstring
        return Screened(
            text="",
            stored=False,
            reason=f"screening failed: {type(error).__name__}",
        )


def build_screen(settings: Settings) -> Screen | None:
    """The screen this deployment should use, or None for no screening.

    None rather than a raise when unconfigured: a developer running against an
    in-memory store has nothing to protect, and making them provision a Model
    Armor template to see the app at all would be security theatre.
    """
    if not settings.configured or not settings.armor_template:
        return None
    return ModelArmorScreen(settings)
