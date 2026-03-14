"""Enhanced EmailTrustScorer with thread encoding and multi-task analysis.

Produces structured ScorerOutput with trust_vector (dict) and Explanation
(reasons array + summary). NOT CoT extraction -- explicit structured output.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import structlog

from autotrust.schemas import Explanation, ScorerOutput

if TYPE_CHECKING:
    from autotrust.config import Spec
    from autotrust.providers import ScoringProvider, TrainingProvider
    from autotrust.schemas import EmailChain

logger = structlog.get_logger()


class EmailTrustScorer:
    """Thread-aware email trust scorer with structured explanation output."""

    def __init__(self, provider: ScoringProvider, spec: Spec) -> None:
        self.provider = provider
        self.spec = spec

    def score_chain(self, chain: EmailChain) -> ScorerOutput:
        """Score a single email chain. Returns trust vector + structured explanation."""
        prompt = self._build_prompt(chain)
        raw_response = self.provider.score(prompt)
        return self._parse_response(raw_response)

    def score_batch(self, chains: list[EmailChain]) -> list[ScorerOutput]:
        """Score multiple chains (sequential)."""
        return [self.score_chain(c) for c in chains]

    def _build_prompt(self, chain: EmailChain) -> str:
        """Build a comprehensive thread-aware scoring prompt with multi-task analysis."""
        
        # Extract comprehensive thread features
        thread_features = self._extract_thread_features(chain)
        
        # Build detailed chain representation
        thread_text = self._format_chain_with_context(chain)
        
        # Create axis-specific analysis sections
        axis_guidance = self._build_axis_guidance()
        
        # Build feature summary
        features_text = self._format_features(thread_features)

        prompt = f"""You are an advanced email security analyzer. Analyze this email chain across multiple trust dimensions using thread-aware analysis.

TRUST AXES TO EVALUATE:
{axis_guidance}

THREAD FEATURES DETECTED:
{features_text}

EMAIL CHAIN:
{thread_text}

ANALYSIS FRAMEWORK:
1. PHISHING INDICATORS: Look for credential harvesting, suspicious links, domain spoofing, brand impersonation
2. MANIPULATION TACTICS: Urgency, authority claims, social engineering, emotional manipulation
3. CLASSIC SPAM: Commercial spam, mass distribution patterns, poor formatting
4. SEARCH VERIFICATION: Claims that should be independently verified before action

For each axis, provide a score from 0.0 (completely safe) to 1.0 (maximum concern).

Respond with a JSON object containing:
1. "trust_vector": a dict mapping each axis name to a float score (0.0-1.0)
2. "explanation": an object with:
   - "reasons": array of axis names that scored > 0.5 (must include all flagged axes)
   - "summary": concise one-sentence summary of primary concerns

CRITICAL: The "reasons" array MUST contain the exact axis names for any axis scoring above 0.5.

JSON Response:"""
        
        return prompt

    def _extract_thread_features(self, chain: EmailChain) -> dict:
        """Extract comprehensive thread-aware features."""
        features = {
            "timing_patterns": [],
            "escalation_signals": [],
            "authority_claims": [],
            "urgency_indicators": [],
            "technical_indicators": [],
            "content_patterns": []
        }

        # Timing analysis
        if len(chain.emails) > 1:
            for i in range(1, len(chain.emails)):
                prev_time = chain.emails[i - 1].timestamp
                curr_time = chain.emails[i].timestamp
                delta = (curr_time - prev_time).total_seconds()
                
                if delta < 300:  # < 5 minutes - very rapid
                    features["timing_patterns"].append(f"Rapid reply: {delta:.0f}s")
                elif delta < 3600:  # < 1 hour - quick
                    features["timing_patterns"].append(f"Quick reply: {delta:.0f}s")

        # Escalation detection
        depths = [e.reply_depth for e in chain.emails]
        if len(set(depths)) > 1:
            features["escalation_signals"].append(f"Thread depth changes: {depths}")

        # Authority and urgency analysis
        all_text = " ".join(e.subject + " " + e.body for e in chain.emails).lower()
        
        # Enhanced authority detection
        authority_patterns = [
            (r'\b(ceo|chief executive)\b', 'CEO claim'),
            (r'\b(cfo|chief financial)\b', 'CFO claim'),
            (r'\b(director|manager|supervisor)\b', 'Management claim'),
            (r'\b(it department|tech support|admin)\b', 'IT authority claim'),
            (r'\b(security team|compliance)\b', 'Security authority claim')
        ]
        
        for pattern, desc in authority_patterns:
            if re.search(pattern, all_text):
                features["authority_claims"].append(desc)

        # Enhanced urgency detection
        urgency_patterns = [
            (r'\b(urgent|immediately|asap|right now)\b', 'Direct urgency'),
            (r'\b(deadline|expires?|time.?sensitive)\b', 'Deadline pressure'),
            (r'\b(act now|don.?t delay|limited time)\b', 'Action urgency'),
            (r'\b(suspend|terminate|close|freeze)\b', 'Account threat')
        ]
        
        for pattern, desc in urgency_patterns:
            if re.search(pattern, all_text):
                features["urgency_indicators"].append(desc)

        # Technical indicators
        if re.search(r'https?://[^\s]+', all_text):
            features["technical_indicators"].append("Contains links")
        
        if re.search(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', all_text):
            features["technical_indicators"].append("Contains email addresses")
            
        if re.search(r'\b(click here|download|install|update)\b', all_text):
            features["technical_indicators"].append("Action-oriented language")

        # Content pattern analysis
        if len(all_text) < 100:
            features["content_patterns"].append("Very brief content")
        elif len(all_text) > 2000:
            features["content_patterns"].append("Lengthy content")
            
        if re.search(r'[A-Z]{3,}', " ".join(e.subject + " " + e.body for e in chain.emails)):
            features["content_patterns"].append("Excessive capitalization")

        return features

    def _format_chain_with_context(self, chain: EmailChain) -> str:
        """Format email chain with enhanced context."""
        thread_parts = []
        
        for i, email in enumerate(chain.emails):
            # Add threading context
            thread_context = f"Position: {i + 1}/{len(chain.emails)}, Reply-depth: {email.reply_depth}"
            
            thread_parts.append(
                f"--- Email {i + 1} ({thread_context}) ---\n"
                f"From: {email.from_addr}\n"
                f"To: {email.to_addr}\n"
                f"Subject: {email.subject}\n"
                f"Timestamp: {email.timestamp}\n"
                f"Content Length: {len(email.body)} chars\n\n"
                f"{email.body}\n"
                f"--- End Email {i + 1} ---"
            )

        return "\n\n".join(thread_parts)

    def _build_axis_guidance(self) -> str:
        """Build detailed guidance for each trust axis."""
        guidance_parts = []
        
        for axis in self.spec.trust_axes:
            if axis.name == "phish":
                guidance = "Phishing detection: credential harvesting, fake login pages, brand impersonation, suspicious domains"
            elif axis.name == "manipulation":
                guidance = "Manipulation tactics: social engineering, emotional pressure, urgency, authority abuse"
            elif axis.name == "classic":
                guidance = "Classic spam: commercial offers, mass distribution, poor formatting, unsolicited promotions"
            elif axis.name == "verify_by_search":
                guidance = "Verification needed: claims requiring independent verification before taking action"
            else:
                guidance = f"General trust assessment for {axis.name}"
            
            guidance_parts.append(f"• {axis.name} (weight: {axis.weight}): {guidance}")
        
        return "\n".join(guidance_parts)

    def _format_features(self, features: dict) -> str:
        """Format extracted features for the prompt."""
        formatted_parts = []
        
        for category, items in features.items():
            if items:
                category_name = category.replace("_", " ").title()
                formatted_parts.append(f"{category_name}: {', '.join(items)}")
        
        return "\n".join(formatted_parts) if formatted_parts else "No specific threat indicators detected"

    def _parse_response(self, raw: str) -> ScorerOutput:
        """Parse LLM response into ScorerOutput with enhanced error handling."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON using balanced-brace matching
            data = self._extract_json(raw)
            if data is None:
                logger.error("Failed to parse response as JSON: %s", raw[:200])
                return self._default_output()

        trust_vector = data.get("trust_vector", {})
        explanation_data = data.get("explanation", {})

        # Ensure all axes are present with proper defaults
        axis_names = {a.name for a in self.spec.trust_axes}
        for axis in self.spec.trust_axes:
            if axis.name not in trust_vector:
                trust_vector[axis.name] = 0.0

        # Clamp values to [0, 1] and filter to known axes
        trust_vector = {
            k: max(0.0, min(1.0, float(v)))
            for k, v in trust_vector.items()
            if k in axis_names
        }

        # Enhanced explanation processing
        reasons = explanation_data.get("reasons", [])
        
        # Ensure reasons include all flagged axes (score > 0.5)
        flagged_axes = [name for name, score in trust_vector.items() if score > 0.5]
        
        # Add any missing flagged axes to reasons
        for axis in flagged_axes:
            if axis not in reasons:
                reasons.append(axis)
        
        # Clean up reasons to only include valid axis names
        valid_reasons = [r for r in reasons if r in axis_names]

        explanation = Explanation(
            reasons=valid_reasons,
            summary=explanation_data.get("summary", "Email chain analyzed for trust indicators."),
        )

        return ScorerOutput(trust_vector=trust_vector, explanation=explanation)

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        """Extract JSON object from raw text using balanced-brace matching."""
        try:
            start = raw.index("{")
        except ValueError:
            return None

        depth = 0
        in_string = False
        escape_next = False
        
        for i in range(start, len(raw)):
            ch = raw[i]
            
            if escape_next:
                escape_next = False
                continue
                
            if ch == "\\":
                escape_next = True
                continue
                
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    
            if depth == 0:
                try:
                    return json.loads(raw[start : i + 1])
                except json.JSONDecodeError:
                    return None
                    
        return None

    def _default_output(self) -> ScorerOutput:
        """Return default output when parsing fails."""
        return ScorerOutput(
            trust_vector={a.name: 0.0 for a in self.spec.trust_axes},
            explanation=Explanation(
                reasons=[], 
                summary="Failed to parse response - defaulting to safe scores."
            ),
        )

    # ---------------------------------------------------------------------------
    # LoRA scaffolding (placeholders)
    # ---------------------------------------------------------------------------

    def fine_tune(self, data_path: str, trainer: TrainingProvider) -> str:
        """Placeholder: LoRA fine-tune via TrainingProvider. Returns checkpoint path."""
        raise NotImplementedError("LoRA fine-tuning not yet implemented")

    def load_fine_tuned(self, checkpoint: str) -> None:
        """Placeholder: Load LoRA checkpoint."""
        raise NotImplementedError("LoRA loading not yet implemented")