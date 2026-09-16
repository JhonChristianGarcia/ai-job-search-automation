import re


def salary_in_range(
    salary_range: str | None = None, desired_salary: int = 60_000
) -> bool:
    """Returns true if the salary range is within or exceeds the desired salary"""
    if not salary_range:
        return True
    if "$" in salary_range or re.search(r"\bUSD\b", salary_range, re.IGNORECASE):
        return True

    salary_pattern = r"(?:₱|PHP)\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"

    salaries = re.findall(salary_pattern, salary_range, re.IGNORECASE)

    if not salaries:
        return False

    salaries = [float(salary.replace(",", "")) for salary in salaries]
    return max(salaries) >= desired_salary


if __name__ == "__main__":
    salary_range = "PHP25,000 - PHP45,000 a month"
    print(salary_in_range(salary_range))
