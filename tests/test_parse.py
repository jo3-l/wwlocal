"""Derived fields the viewer relies on. Compensation cases are real postings' text."""

import pytest

from wwlocal.parse import (
    compensation,
    duration_key,
    external_application,
    facets,
    field_text,
    rating_summary,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$22-$26 per hour", {"lo": 22, "hi": 26, "unit": "hr", "currency": None}),
        ("$22 per hour", {"lo": 22, "hi": None, "unit": "hr", "currency": None}),
        ("$26-32/hour", {"lo": 26, "hi": 32, "unit": "hr", "currency": None}),
        ("$35.00/hour 40 hours/week", {"lo": 35, "hi": None, "unit": "hr", "currency": None}),
        (
            "Hourly rate: $40-50 USD/hour depending on experience",
            {"lo": 40, "hi": 50, "unit": "hr", "currency": "USD"},
        ),
        (
            "Compensation for this role ranges from CAD $40 to $46/hour.",
            {"lo": 40, "hi": 46, "unit": "hr", "currency": "CAD"},
        ),
        (
            "USD$40/hour (CAD$55+/hour) meals covered",
            {"lo": 40, "hi": None, "unit": "hr", "currency": "USD"},
        ),
        ("Hourly Wage: $35 to $40 CAD", {"lo": 35, "hi": 40, "unit": "hr", "currency": "CAD"}),
        (
            "Salary: $2,461/week USD (yes, we pay weekly)",
            {"lo": 2461, "hi": None, "unit": "wk", "currency": "USD"},
        ),
        (
            "The salary range for the position is $656.97 - $875.96 per week",
            {"lo": 656.97, "hi": 875.96, "unit": "wk", "currency": None},
        ),
        (
            "4th term: CAD $8,400/month 5th term: CAD $8,800/month",
            {"lo": 8400, "hi": None, "unit": "mo", "currency": "CAD"},
        ),
        ("$5K - $12.5K USD per month", {"lo": 5000, "hi": 12500, "unit": "mo", "currency": "USD"}),
        (
            "Pay is set to $7,000 USD per month",
            {"lo": 7000, "hi": None, "unit": "mo", "currency": "USD"},
        ),
        (
            "Negotiable, typically $1,400 / week or $72,800 annualized",
            {"lo": 1400, "hi": None, "unit": "wk", "currency": None},
        ),
        ("€2,500 per month", {"lo": 2500, "hi": None, "unit": "mo", "currency": "EUR"}),
        # bare numbers with no currency and no unit are not pay
        ("expected 40 working hours / week", None),
        ("We offer a competitive salary based on employment history.", None),
        ("2 years of experience", None),
        ("", None),
    ],
)
def test_compensation(text, expected):
    assert compensation(text) == expected


def test_field_text_prefers_text_over_html():
    assert field_text({"html": "<p>a<br>b</p>", "text": "a\n\nb"}) == "a b"
    assert field_text({"html": "<p>a<br>b</p>"}) == "a b"
    assert field_text({"list": ["Resume", "Cover Letter"]}) == "Resume Cover Letter"
    assert field_text("  x  ") == "x"
    assert field_text(None) == ""


@pytest.mark.parametrize(
    ("d", "key"),
    [
        (None, "unspecified"),
        ("4 month work term", "4 months"),
        ("8 month work term preferred", "8 months preferred"),
        ("8 month work term required", "8 months required"),
        ("12 month work term", "12 month work term"),
    ],
)
def test_duration_key(d, key):
    assert duration_key(d) == key


def test_facets_fall_back_to_summary_level():
    f = facets({"level": "Intermediate, Senior"}, None)
    assert f["levels"] == ["Intermediate", "Senior"]
    assert f["arrangement"] == f["region"] == f["country"] == "unspecified"
    assert f["duration"] == "unspecified"
    assert f["clusters"] == [] and f["docs"] == []


def test_facets_from_detail():
    f = facets(
        {"level": "Junior"},
        {
            "levels": ["Senior"],
            "location_arrangement": "Remote",
            "region": "USA - West",
            "address": {"country": "United States"},
            "work_term_duration": "4 month work term",
            "targeted_clusters": ["- Theme - Computing: Software", "ENG - Software Engineering"],
            "documents_required": ["Résumé", "Cover Letter"],
        },
    )
    assert f == {
        "arrangement": "Remote",
        "region": "USA - West",
        "country": "United States",
        "levels": ["Senior"],
        "duration": "4 months",
        "clusters": ["Computing: Software", "ENG - Software Engineering"],
        "docs": ["Résumé", "Cover Letter"],
        "apply": "WaterlooWorks only",
    }


REPORT = {
    "tables": [
        {
            "title": "Hiring History",
            "columns": ["", "Students Hired", "2025 - Fall", "2026 - Winter", "2026 - Spring"],
            "rows": [
                ["Employer Organization", "Acme", "3", "0", "5"],
                ["Employer Division", "Acme - Widgets", "1", "0", "2"],
            ],
        },
        {
            "title": "Work Term Ratings Summary",
            "columns": ["", "x", "Average Work Term Satisfaction Rating", "Number Of Ratings"],
            "rows": [
                ["Employer Organization", "Acme", "8.4", "83"],
                ["Employer Division", "Acme - Widgets", "N/A", "2"],
                ["All Co-op Students Average", "x", "8.5", "45728"],
            ],
        },
    ],
    "charts": [
        {
            "title": "Most Frequently Hired Programs - Acme",
            "categories": ["CS", "SE"],
            "series": [{"data": [10, 4], "name": "Hires"}],
        },
        {
            "title": "Overall Work Term Satisfaction - Distribution<br>Fall 2023 to Spring 2026",
            "categories": ["1", "2"],
            "series": [{"data": [0, 100], "name": "Acme"}],
        },
        {
            "title": "Average Rating by Question (1-5 scale)<br>Fall 2023 to Spring 2026",
            "categories": ["Q1. Support", "Q2. Learning"],
            "series": [
                {"data": [4.5, 4.4], "name": "Average of All Co-op Students", "type": "spline"},
                {"data": [4.8, 4.9], "name": "Acme", "type": "column"},
            ],
        },
    ],
}


def test_rating_summary():
    r = rating_summary(REPORT)
    assert r["terms"] == ["2025 - Fall", "2026 - Winter", "2026 - Spring"]
    assert r["org_hires"] == [3, 0, 5] and r["div_hires"] == [1, 0, 2]
    assert r["hires_total"] == 8 and r["hires_recent"] == 8
    assert r["rating"] == 8.4 and r["rating_n"] == 83 and r["all_avg"] == 8.5
    assert r["div_rating"] is None and r["div_n"] == 2
    assert r["programs"] == [("CS", 10), ("SE", 4)]
    assert r["dist"] == [("1", 0), ("2", 100)]
    assert r["questions"] == [("Q1. Support", 4.8, 4.5), ("Q2. Learning", 4.9, 4.4)]
    assert r["questions_range"] == "Fall 2023 to Spring 2026"


def test_rating_summary_falls_back_to_division_and_handles_nothing():
    only_div = {
        "tables": [
            {
                "title": "Work Term Ratings Summary",
                "columns": [],
                "rows": [["Employer Division", "x", "7.0", "3"]],
            }
        ],
        "charts": [],
    }
    r = rating_summary(only_div)
    assert r["rating"] == 7 and r["rating_n"] == 3
    empty = rating_summary(None)
    assert empty["rating"] is None and empty["org_hires"] == [] and empty["programs"] is None


@pytest.mark.parametrize(
    ("field", "method", "expected"),
    [
        # the co-op office's stock sentence, link on its own line
        (
            {
                "text": "Interested applicants must apply through WaterlooWorks and directly to the"
                " employer to be considered for this position:\nhttps://jobs.ashbyhq.com/x/1"
            },
            "WaterlooWorks",
            {"url": "https://jobs.ashbyhq.com/x/1", "email": None, "why": "ats"},
        ),
        # link only in an href behind "HERE"
        (
            {
                "text": "In addition to submitting your application in WaterlooWorks, apply HERE.",
                "html": '<p>… apply <a href="https://job-boards.greenhouse.io/co/jobs/1">HERE</a>.</p>',
            },
            "WaterlooWorks",
            {"url": "https://job-boards.greenhouse.io/co/jobs/1", "email": None, "why": "ats"},
        ),
        # bare ATS link, no instruction at all
        (
            {"text": "https://grnh.se/abc\n\nOur interview process is three steps."},
            "WaterlooWorks",
            {"url": "https://grnh.se/abc", "email": None, "why": "ats"},
        ),
        # boilerplate, apply by email
        (
            {
                "text": "Interested applicants must apply through WaterlooWorks and directly to the"
                " employer: info@example.com with your name in the subject."
            },
            "WaterlooWorks",
            {"url": None, "email": "info@example.com", "why": "boilerplate"},
        ),
        # boilerplate with a non-ATS careers link
        (
            {
                "text": "Please apply directly through our careers page at this link.",
                "html": 'apply directly through our <a href="https://co.com/careers?id=1">careers</a>',
            },
            "WaterlooWorks",
            {"url": "https://co.com/careers?id=1", "email": None, "why": "boilerplate"},
        ),
        # a structured method other than WaterlooWorks
        ({"text": ""}, "Employer's Website", {"url": None, "email": None, "why": "method"}),
        # links that are not applications
        (
            {"text": "Applying students must be eligible: https://canada.diplo.de/visa/yma"},
            "WaterlooWorks",
            None,
        ),
        ({"text": "Founders: https://www.linkedin.com/in/someone/"}, "WaterlooWorks", None),
        ({"text": "Employer will be contacting you directly."}, "WaterlooWorks", None),
        (None, None, None),
    ],
)
def test_external_application(field, method, expected):
    fields = {"additional_application_information": field} if field is not None else None
    detail = {"application_method": method} if method else None
    assert external_application(fields, detail) == expected


def test_facets_apply_value():
    assert facets({}, None)["apply"] == "WaterlooWorks only"
    assert facets({}, None, {"url": "x"})["apply"] == "Also on employer site"
