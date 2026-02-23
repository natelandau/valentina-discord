"""String utilities."""

from vclient.models import CampaignExperience, RollStatistics


def num_to_circles(num: int = 0, maximum: int = 5) -> str:
    """Return the emoji corresponding to the number. When `num` is greater than `maximum`, the `maximum` is increased to `num`.

    Args:
        num (int, optional): The number to convert. Defaults to 0.
        maximum (int, optional): The maximum number of circles. Defaults to 5.

    Returns:
        str: A string of circles and empty circles. i.e. `●●●○○`
    """
    if num is None:
        num = 0
    if maximum is None:
        maximum = 5
    maximum = max(num, maximum)

    return "●" * num + "○" * (maximum - num)


def truncate_string(text: str, max_length: int = 1000) -> str:
    """Truncate a string to a maximum length.

    Args:
        text (str): The string to truncate.
        max_length (int, optional): The maximum length of the string. Defaults to 1000.

    Returns:
        str: The truncated string.
    """
    if len(text) > max_length:
        return text[: max_length - 4] + "..."
    return text


def convert_int_to_emoji(*, num: int, as_shortcode: bool = False) -> str:
    """Convert an integer to a unicode emoji or a string.

    This method converts an integer to its corresponding emoji representation if it is between 0 and 10. For integers outside this range, it returns the number as a string. Optionally, it can wrap numbers larger than emojis within in markdown <pre> markers.

    Args:
        num (int): The integer to convert.
        as_shortcode (bool, optional): Whether to return a shortcode instead of a unicode emoji. Defaults to False.

    Returns:
        str: The emoji corresponding to the integer, or the integer as a string.

    """
    if not (0 <= num <= 10):  # noqa: PLR2004
        return f"`{num}`" if as_shortcode else str(num)

    emoji_map = {
        0: (":zero:", "0️⃣"),
        1: (":one:", "1️⃣"),
        2: (":two:", "2️⃣"),
        3: (":three:", "3️⃣"),
        4: (":four:", "4️⃣"),
        5: (":five:", "5️⃣"),
        6: (":six:", "6️⃣"),
        7: (":seven:", "7️⃣"),
        8: (":eight:", "8️⃣"),
        9: (":nine:", "9️⃣"),
        10: (":keycap_ten:", "🔟"),
    }

    shortcode, unicode_emoji = emoji_map[num]
    if as_shortcode:
        return shortcode if num == 10 else f"{shortcode}"  # noqa: PLR2004
    return unicode_emoji


def statistics_to_markdown(statistics: RollStatistics, *, with_help: bool = False) -> str:
    """Convert a statistics object to a markdown string.

    Args:
        statistics (RollStatistics): The statistics object to convert.
        with_help (bool, optional): Whether to include the help text. Defaults to False.

    Returns:
        str: The markdown string.
    """
    if statistics.total_rolls == 0:
        return "No statistics found"

    msg = f"""\
`Total Rolls {".":.<{25 - 12}} {statistics.total_rolls}`
`Critical Success Rolls {".":.<{25 - 23}} {statistics.criticals:<3} ({statistics.criticals_percentage:.2f}%)`
`Successful Rolls {".":.<{25 - 17}} {statistics.successes:<3} ({statistics.success_percentage:.2f}%)`
`Failed Rolls {".":.<{25 - 13}} {statistics.failures:<3} ({statistics.failure_percentage:.2f}%)`
`Botched Rolls {".":.<{25 - 14}} {statistics.botches:<3} ({statistics.botch_percentage:.2f}%)`
"""

    if with_help:
        msg += """
> Definitions:
> - _Critical Success_: More successes than dice rolled
> - _Success_: At least one success after all dice are tallied
> - _Failure_: Zero successes after all dice are tallied
> - _Botch_: Negative successes after all dice are tallied
"""
    return msg


def experience_to_markdown(experience: CampaignExperience) -> str:
    """Convert the campaign experience to a markdown string."""
    return f"""```scala
Current XP:  {experience.xp_current}
Lifetime CP: {experience.cool_points}
Lifetime XP: {experience.xp_total}
```"""
