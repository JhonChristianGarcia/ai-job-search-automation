import re


def salary_in_range(salary_range: str | None= None, desired_salary: int = 60_000) -> bool:
    if not salary_range:
        return True
    salary_pattern = r"₱\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
    salaries = re.findall(salary_pattern, salary_range)
    print(salaries)
    if not salaries:
        return False

    salaries = [float(salary.replace(",", "")) for salary in salaries]

    return max(salaries) >= desired_salary    

if __name__ == "__main__":
    salary_range = "PHP40,000 – PHP165,000 per month"
    print(salary_in_range()) 