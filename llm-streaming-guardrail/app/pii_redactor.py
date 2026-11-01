
import re


REDACTION = "[REDACTED]"
HOLD_BACK = 260

EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"[A-Za-z0-9._%+-]{1,64}@"
    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"(?![A-Za-z0-9_-])"
)

SSN_PATTERN = re.compile(
    r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"
)

CARD_PATTERN = re.compile(
    r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
)


def luhn_check(number: str) -> bool:
    """Validate a credit card candidate using Luhn."""
    digits = [int(c) for c in number if c.isdigit()]

    if not 13 <= len(digits) <= 19:
        return False

    total = 0

    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2

            if digit > 9:
                digit -= 9

        total += digit

    return total % 10 == 0


class StreamingPIIRedactor:

    def __init__(self):
        self.buffer = ""

    def find_matches(self, text):
        matches = []

        for pattern in (EMAIL_PATTERN, SSN_PATTERN):
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end()))

        for match in CARD_PATTERN.finditer(text):
            if luhn_check(match.group()):
                matches.append((match.start(), match.end()))

        # Merge overlapping matches.
        matches.sort()

        merged = []

        for start, end in matches:
            if merged and start < merged[-1][1]:
                previous_start, previous_end = merged[-1]
                merged[-1] = (
                    previous_start,
                    max(previous_end, end)
                )
            else:
                merged.append((start, end))

        return merged

    def redact_prefix(self, text, matches, safe_length):
        """Redact matches without splitting a sensitive value."""

        output = []
        cursor = 0

        for start, end in matches:
            if end > safe_length:
                break

            output.append(text[cursor:start])
            output.append(REDACTION)
            cursor = end

        output.append(text[cursor:safe_length])

        return "".join(output)

    def push(self, chunk):
        self.buffer += chunk

        safe_length = max(
            0,
            len(self.buffer) - HOLD_BACK
        )

        matches = self.find_matches(self.buffer)

        # Do not split a detected sensitive value.
        for start, end in matches:
            if start < safe_length < end:
                safe_length = start

        if safe_length == 0:
            return ""

        safe_output = self.redact_prefix(
            self.buffer,
            matches,
            safe_length
        )

        self.buffer = self.buffer[safe_length:]

        return safe_output

    def flush(self):
        """Process the remaining text when the stream ends."""

        remaining = self.buffer

        self.buffer = ""

        matches = self.find_matches(remaining)

        return self.redact_prefix(
            remaining,
            matches,
            len(remaining)
        )
