from app.jobs.normalize import NormalizedJob, dedupe_key, deduplicate, enrich, parse_salary_text, strip_html
from app.jobs.providers import adzuna_to_job, ashby_to_job, greenhouse_to_job, jsearch_to_job, lever_to_job
from app.jobs.skills import extract_skills, split_required_preferred
from app.jobs.synthetic import synthetic_jobs


def test_skill_extraction_and_required_preferred():
    req, pref = split_required_preferred("Must have Python, RAG and Kubernetes. Nice to have: Terraform and Go lang.")
    assert {"Python", "RAG", "Kubernetes"} <= set(req)
    assert "Terraform" in pref and "Python" not in pref
    assert "Java" not in extract_skills("We use JavaScript")


def test_salary_parsing_never_guesses():
    assert parse_salary_text("Pay: CAD 150,000 - 180,000 per year") == (150000, 180000, "CAD")
    assert parse_salary_text("$140k-$170k", "USD") == (140000, 170000, "USD")
    assert parse_salary_text("$45 - $60 per hour") is None  # hourly: not presented as annual
    assert parse_salary_text("competitive salary") is None


def test_html_stripped():
    assert strip_html("<p>Hello<br/>world &amp; co</p>") == "Hello\nworld & co"


def test_provider_mapping_and_adzuna_predicted_salary_not_verified():
    j = jsearch_to_job({"job_id": "x1", "job_title": "Senior AI Engineer", "employer_name": "Acme", "job_city": "Toronto",
                        "job_country": "CA", "job_publisher": "LinkedIn", "job_min_salary": 150000, "job_max_salary": 180000,
                        "job_salary_currency": "CAD", "job_salary_period": "YEAR", "job_description": "Python and RAG",
                        "job_apply_link": "https://example.com/a"})
    assert j.origin_publisher == "LinkedIn" and j.salary_verified and j.seniority == "senior"
    a = adzuna_to_job({"id": 5, "title": "ML Engineer", "company": {"display_name": "B"}, "salary_min": 90000, "salary_max": 100000,
                       "salary_is_predicted": "1", "description": "", "location": {"display_name": "Toronto", "area": ["Canada", "Toronto"]}}, "ca")
    assert a.salary_min is None and not a.salary_verified
    g = greenhouse_to_job({"id": 1, "title": "Data Scientist", "content": "&lt;p&gt;SQL&lt;/p&gt;", "location": {"name": "Remote"},
                           "absolute_url": "https://boards.greenhouse.io/x/jobs/1"}, "x", "X Corp")
    assert g.source == "greenhouse" and "SQL" in g.required_skills and g.work_arrangement == "remote"
    lv = lever_to_job({"id": "abc", "text": "Backend Engineer", "categories": {"location": "Toronto"}, "descriptionPlain": "Python",
                       "salaryRange": {"min": 120000, "max": 140000, "currency": "CAD", "interval": "per-year-salary"},
                       "hostedUrl": "https://jobs.lever.co/x/abc", "createdAt": 1700000000000}, "x", "X")
    assert lv.salary_verified and lv.posted_at is not None
    ab = ashby_to_job({"id": "q", "title": "AI Engineer", "isRemote": True, "descriptionPlain": "LLMs",
                       "compensation": {"summaryComponents": [{"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD",
                                                               "minValue": 1, "maxValue": 2}]}}, "b", "B")
    assert ab.work_arrangement == "remote" and ab.salary_currency == "USD"


def test_dedupe_prefers_employer_board_and_keeps_salary():
    base = dict(company="Acme Inc.", title="Sr. AI Engineer", city="Toronto")
    agg = enrich(NormalizedJob(source="jsearch", source_job_id="1", salary_min=150000, salary_max=170000, salary_currency="CAD",
                               salary_verified=True, **base))
    board = enrich(NormalizedJob(source="greenhouse", source_job_id="2", company="ACME", title="Senior AI Engineer", city="Toronto"))
    out = deduplicate([agg, board])
    assert len(out) == 1 and out[0].source == "greenhouse" and out[0].salary_min == 150000
    assert dedupe_key("Acme Inc", "Sr AI Engineer", "Toronto, ON") == dedupe_key("acme", "Senior AI Engineer", "Toronto")


def test_synthetic_jobs_are_labelled():
    jobs = synthetic_jobs()
    assert len(jobs) == 100 and all(j.is_synthetic and "(Demo)" in j.company for j in jobs)
    assert all(j.apply_url.startswith("https://example.com/") for j in jobs)


def test_query_keeps_acronyms_and_matches_whole_words():
    from types import SimpleNamespace as N

    from app.jobs.providers import SearchFilters
    from app.jobs.search import apply_filters

    def job(title):
        return N(title=title, company="X", city="Toronto", location="Toronto", country="CA", work_arrangement="onsite", seniority="senior",
                 industry=None, employment_type=None, required_skills=[], preferred_skills=[], posted_at=None, salary_min=None,
                 salary_max=None, salary_verified=False, salary_currency=None)
    out, _ = apply_filters([job("Senior AI Engineer"), job("Staff Data Engineer"), job("Email Maintainer")], SearchFilters(query="Senior AI Engineer"))
    assert [j.title for j in out] == ["Senior AI Engineer"]
