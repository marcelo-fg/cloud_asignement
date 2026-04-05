import re

def normalize_title(title: str) -> str:
    """
    Normalizes a MovieLens title by moving "The", "A", or "An" to the front.
    Also strips the trailing year "(YYYY)" if present.
    Examples:
      "Matrix, The (1999)"        -> "The Matrix"
      "Dark Knight, The (2008)"   -> "The Dark Knight"
      "Matrix, The"               -> "The Matrix"
      "Inception (2010)"          -> "Inception"
    """
    if not title:
        return title

    # Strip trailing year "(YYYY)" if present
    year_match = re.search(r"\s*\(\d{4}\)\s*$", title)
    if year_match:
        title = title[:year_match.start()].strip()

    # Move ", The / , A / , An" from end to front
    article_match = re.search(r",\s*(The|A|An)$", title, re.IGNORECASE)
    if article_match:
        article = article_match.group(1)
        main_title = title[:article_match.start()].strip()
        return f"{article} {main_title}"

    return title
