# Dependency Health Monitor - Scoring Algorithm Analysis

**Date:** 27 January 2026
**Author:** Architecture Review
**Files Analyzed:**
- `src/dhm/core/calculator.py`
- `src/dhm/core/models.py`
- `src/dhm/collectors/github.py`
- `src/dhm/collectors/pypi.py`
- `src/dhm/collectors/vulnerability.py`

---

## 1. Weight Distribution Analysis

### Current Weights

| Component     | Weight | Contribution to Final Score |
|---------------|--------|------------------------------|
| Security      | 0.35   | 35%                          |
| Maintenance   | 0.30   | 30%                          |
| Community     | 0.20   | 20%                          |
| Popularity    | 0.15   | 15%                          |

**Note:** `code_quality_score` is calculated but NOT included in the weighted overall score. This appears to be an oversight or future placeholder.

### Weight Analysis

**Strengths:**
- Security being highest (35%) is appropriate for a dependency health tool
- Maintenance (30%) being second makes sense for long-term viability
- Total weights sum to 1.0 with normalization

**Concerns:**
- **Code Quality is Orphaned:** The `_calculate_quality_score()` method is called but its result is only stored in `code_quality_score`, never contributing to `overall`. This is wasted computation and misleading since users see this score.
- **Community vs Popularity Overlap:** Both scores use `stars` as a factor, causing double-counting for highly-starred repos.

### Missing Factors

1. **License Compatibility** - No scoring for permissive vs restrictive licenses
2. **Python Version Support** - Whether package supports current Python versions
3. **Documentation Quality** - No assessment of docs presence/quality
4. **Test Coverage** - Not evaluated (mentioned as future work in code comments)
5. **CI/CD Status** - No checking of build badges or CI health
6. **Typosquatting Risk** - No assessment of package name legitimacy
7. **Dependency Depth** - How many transitive dependencies a package brings

---

## 2. Component Score Calculations

### 2.1 Security Score

**Location:** `_calculate_security_score()` (lines 120-153)

**Algorithm:**
```
Base: 100.0

For each OPEN vulnerability:
  - CRITICAL: -40 points
  - HIGH:     -25 points
  - MEDIUM:   -10 points
  - LOW:      -5 points
  - INFO:     -1 point

For each FIXED vulnerability:
  - Apply only 10% of the normal deduction (historical penalty)

Floor: 0.0
```

**Inputs:**
- List of `Vulnerability` objects
- Each vulnerability has `is_open` property (True if affects installed version)
- Severity levels from `RiskLevel` enum

**Score Ranges:**
- 100: No vulnerabilities
- 90: One medium open vulnerability
- 60: One critical open vulnerability
- 35: One critical + one high open vulnerability
- 0: Multiple severe vulnerabilities

**Edge Cases:**
- Empty vulnerability list: Returns 100.0 (correct)
- Unknown severity: Defaults to 5-point deduction

**Issues Identified:**
1. **No Score Floor per Vulnerability Type:** A package with 3 critical vulns scores 0, same as one with 10 critical vulns. No differentiation after floor is hit.
2. **Historical Deduction is Too Light:** Fixed vulnerabilities only deduct 10% - a package that had 10 critical vulnerabilities (all fixed) loses only 4 points total. This may be too lenient for packages with a history of security issues.

---

### 2.2 Maintenance Score

**Location:** `_calculate_maintenance_score()` (lines 155-217)

**Algorithm:**
```
Base: 50.0

Release Recency (PyPI data):
  < 30 days:   +20 points
  < 90 days:   +15 points
  < 180 days:  +10 points
  < 365 days:  +5 points
  > 730 days:  -10 points (2+ years old)

Release Count (PyPI data):
  > 10 releases: +10 points
  > 5 releases:  +5 points

Deprecation (PyPI classifiers):
  If deprecated: -20 points

Commit Frequency (GitHub data):
  > 1 commit/day:   +15 points
  > 0.1 commit/day: +10 points
  > 0 commit/day:   +5 points

Issue Responsiveness (GitHub data):
  > 80% close rate: +10 points
  > 50% close rate: +5 points

Archived Status (GitHub data):
  If archived: -30 points

Floor: 0.0
Ceiling: 100.0
```

**Score Ranges:**
- Maximum achievable: 100 (50 + 20 + 10 + 15 + 10 = 105, capped at 100)
- Minimum achievable: 0 (50 - 10 - 20 - 30 = -10, floored at 0)

**Critical Issues:**

1. **PyPI-only packages get penalized:** Without GitHub data, max maintenance score is:
   - Base 50 + 20 (recent) + 10 (releases) = 80
   - Missing 15 (commits) + 10 (issue close rate) = 25 potential points

2. **Stable Packages are Punished:** A mature, stable package that needs no changes (e.g., `click`) will lose points for:
   - Not having commits in last 30 days (misses +15)
   - Potentially old release date (may lose points or miss +20)

3. **Gap in Release Date Scoring:** No bonus for 365-730 day range, only penalty after 730 days. This creates a "dead zone" where packages score the same whether released 366 or 729 days ago.

---

### 2.3 Community Score

**Location:** `_calculate_community_score()` (lines 219-264)

**Algorithm:**
```
Base: 0.0 (NOT 50!)

Contributors:
  > 100: +30 points
  > 20:  +25 points
  > 5:   +20 points
  > 1:   +10 points

Stars:
  > 10,000: +30 points
  > 1,000:  +25 points
  > 100:    +15 points
  > 10:     +5 points

Forks:
  > 100: +20 points
  > 10:  +10 points

PR Merge Rate (90 days):
  > 70%: +20 points
  > 40%: +10 points

No Repository Data: Returns 50.0 (neutral)

Ceiling: 100.0
```

**Score Ranges:**
- Maximum achievable: 100 (30 + 30 + 20 + 20 = 100)
- Minimum with repo data: 0 (small project with 1 contributor, few stars/forks, low PR merge)
- Without repo data: 50.0

**Critical Issues:**

1. **Base of 0 vs 50:** This is the BIGGEST problem. Community score starts at 0, while other scores start at 50. This means:
   - A package with a small GitHub presence (2 contributors, 50 stars, 5 forks) scores only ~20-25
   - This dramatically drags down the overall score

2. **No Repository = 50, Small Repository = Lower:** A package without GitHub data gets 50, but a package with a small GitHub repo gets penalized MORE. This is backwards - having some community is better than none.

3. **Single Maintainer Gets 10 Points:** A solo developer project scores 10 for contributors. Many excellent packages are maintained by one person.

4. **Star Thresholds are Extreme:**
   - Need 10,000+ stars for max points
   - Only 5 points for 11-100 stars
   - Many excellent packages have 500-1000 stars and get only 15 points

---

### 2.4 Popularity Score

**Location:** `_calculate_popularity_score()` (lines 266-307)

**Algorithm:**
```
Base: 0.0

Downloads (PyPI data):
  > 10M/month: +50 points
  > 1M/month:  +40 points
  > 100K/month:+30 points
  > 10K/month: +20 points
  > 1K/month:  +10 points
  > 100/month: +5 points

Watchers (GitHub data):
  > 1000: +30 points
  > 100:  +20 points
  > 10:   +10 points

Star Bonus (GitHub data):
  > 5000 stars: +20 points

Ceiling: 100.0
```

**Critical Issues:**

1. **Downloads Default to 0:** In `pypi.py` line 195, `_estimate_downloads()` ALWAYS returns 0. Downloads are only populated if `get_download_stats()` is called separately. This is a MAJOR BUG - if pypistats.org call fails or isn't made, downloads = 0 and popularity tanks.

2. **Base of 0:** Same problem as community - starts at 0, not 50.

3. **Without PyPI Data:** If PyPI data is missing and only repo data exists, max score is 50 (30 watchers + 20 star bonus). This is a failure mode.

4. **Double-counting Stars:** Stars contribute to both Community score AND Popularity score (as star bonus). This gives disproportionate weight to GitHub popularity.

---

### 2.5 Code Quality Score (ORPHANED)

**Location:** `_calculate_quality_score()` (lines 309-345)

**Algorithm:**
```
Base: 50.0

Contributors:
  > 5: +15 points
  > 2: +10 points

PR Merge Rate:
  > 60%: +15 points
  > 30%: +10 points

Issue Close Time:
  < 7 days:  +10 points
  < 30 days: +5 points

Original Work:
  Not a fork: +10 points

No Repository Data: Returns 50.0

Floor: 0.0
Ceiling: 100.0
```

**Critical Issue:** This score is NEVER USED in the overall calculation! It's computed and stored but has zero impact on the final grade.

---

## 3. Grade Thresholds

**Location:** `_score_to_grade()` (lines 391-402)

| Grade | Score Range | Description       |
|-------|-------------|-------------------|
| A     | 90-100      | Excellent         |
| B     | 80-89       | Good              |
| C     | 70-79       | Acceptable        |
| D     | 60-69       | Concerning        |
| F     | 0-59        | Critical          |

### Threshold Analysis

**Problem:** The thresholds assume scores are normally distributed around 75-80. But due to the scoring algorithm issues:

1. **Community Score Base of 0** pulls scores down
2. **Popularity Score often 0** (due to download bug) pulls scores down
3. **Missing GitHub Data** causes multiple 50 defaults but community starts at 0

**Typical Score Calculation for a "Good" Package WITHOUT GitHub data:**
```
Security:    100 * 0.35 = 35.0   (no vulns)
Maintenance:  75 * 0.30 = 22.5   (good PyPI data)
Community:    50 * 0.20 = 10.0   (default, no repo)
Popularity:   20 * 0.15 =  3.0   (some downloads, but likely 0)
                         ------
Total:                   70.5    = Grade C
```

**This is why Click, pytest, and rich get C grades!**

---

## 4. Why Well-Known Packages Get C Grades

### Root Causes

#### 4.1 The Download Data Bug

In `/home/jay/Documents/cyber/dev/planning_studio/dependency_health_monitor/src/dhm/collectors/pypi.py`:

```python
def _estimate_downloads(self, data: dict[str, Any]) -> int:
    """Estimate monthly downloads from available data.

    PyPI doesn't provide download stats directly. We return 0 here
    and fetch from pypistats.org separately in get_download_stats().
    """
    return 0  # ALWAYS RETURNS 0!
```

The `get_download_stats()` method exists but must be called separately. If it's not called, or if pypistats.org is unavailable, `downloads_last_month` stays at 0.

**Impact:** A package with 50 million downloads scores 0 points for downloads in the popularity calculation.

#### 4.2 GitHub Rate Limiting

Without a `GITHUB_TOKEN`, GitHub API allows only 60 requests/hour. When rate-limited:

```python
if isinstance(commits, Exception):
    commits = []
if isinstance(issues, Exception):
    issues = {"close_rate": 0.0, "avg_close_time": 0.0}
if isinstance(prs, Exception):
    prs = {"merge_rate": 0.0, "avg_merge_time": 0.0, "open_count": 0}
if isinstance(contributors, Exception):
    contributors = 0
```

**Impact:** All GitHub metrics default to 0, not sensible fallbacks. This means:
- `commit_frequency_30d = 0` (loses 15 maintenance points)
- `issue_close_rate_90d = 0` (loses 10 maintenance points)
- `contributors_count = 0` (loses all community points from contributors)
- `pr_merge_rate_90d = 0` (loses community and quality points)

#### 4.3 Community Score Starts at 0

For a package like `click` with modest GitHub metrics (say 15k stars, 100 contributors, 200 forks):
```
Contributors > 100:    +30
Stars > 10,000:        +30
Forks > 100:           +20
PR Merge Rate > 70%:   +20
                       ----
Total:                 100 (capped)
```

But if GitHub data is MISSING (rate limited or no repo URL found):
- Returns 50.0

If GitHub data is PARTIAL (repo found but API calls failed):
- Stars from main repo call might be present: +30
- Contributors call failed: +0
- PR stats failed: +0
- Total: ~30-50

This creates a perverse incentive where having a GitHub repo but failing to fetch full data scores LOWER than having no GitHub repo at all.

#### 4.4 "Mature, Stable" Package Penalty

A mature package like `click` that is stable and doesn't need frequent changes gets penalized:

- Last release: Maybe 6+ months ago -> only +5 or +10 for release recency (not +20)
- Commits per day: Maybe 0.05 -> +5 (not +15)
- These packages ARE healthy but the algorithm penalizes stability

### Worked Example: Click Package (Hypothetical)

**Assumptions:**
- No open vulnerabilities
- Last release: 180 days ago
- 50 releases total
- GitHub: 15k stars, 100 contributors, 200 forks
- Downloads: 30M/month (but bug makes this 0)
- Commits in last 30 days: 5 (0.17/day)
- Issue close rate: 60%
- PR merge rate: 65%

**Security Score:** 100.0 (no vulns)

**Maintenance Score:**
```
Base:                   50
Release < 180 days:    +10
Releases > 10:         +10
Commits > 0.1/day:     +10
Issue close > 50%:     +5
                       ---
Total:                  85
```

**Community Score:**
```
Contributors > 100:    +30
Stars > 10,000:        +30
Forks > 100:           +20
PR merge > 40%:        +10 (not > 70%, so only +10)
                       ---
Total:                  90
```

**Popularity Score:**
```
Downloads (BUG = 0):   +0   <-- Should be +40 for 30M
Watchers (say 500):    +20
Stars > 5000:          +20
                       ---
Total:                  40  <-- Should be 80+
```

**Overall Calculation:**
```
Security:    100 * 0.35 = 35.0
Maintenance:  85 * 0.30 = 25.5
Community:    90 * 0.20 = 18.0
Popularity:   40 * 0.15 =  6.0  <-- Should be 12.0
                         ------
Total:                   84.5   <-- Grade B

With downloads bug fixed: 90.5 = Grade A
```

Even in this best-case scenario with all data available, the download bug drops Click from an A to a B. With GitHub rate limiting or missing data, it easily falls to C.

---

## 5. Data Dependencies and Failure Modes

### 5.1 PyPI Data Unavailable

**What happens:**
- `pypi` parameter is `None`
- Maintenance score: Base 50 only (no release date, no release count)
- Popularity score: 0 from downloads (can only get points from GitHub watchers/stars)

**Defaults Applied:**
- No explicit defaults in calculator - it checks `if pypi:` before using values

**Impact:** Severe. Maintenance score capped around 50-65 (only from GitHub data), popularity score capped around 50 (only from GitHub).

### 5.2 GitHub Data Unavailable (Rate Limited)

**What happens:**
- `repo` parameter is `None` OR all nested API calls fail
- Maintenance: Loses commit_frequency and issue_close_rate contributions
- Community: Returns 50.0 (neutral) if `repo is None`, BUT if repo exists with zeroed metrics, scores near 0
- Popularity: Loses watchers and star bonus
- Quality: Returns 50.0 (unused anyway)

**Defaults Applied:**
```python
# In github.py lines 104-111
if isinstance(commits, Exception):
    commits = []
if isinstance(issues, Exception):
    issues = {"close_rate": 0.0, "avg_close_time": 0.0}
if isinstance(prs, Exception):
    prs = {"merge_rate": 0.0, "avg_merge_time": 0.0, "open_count": 0}
if isinstance(contributors, Exception):
    contributors = 0
```

**Impact:** Moderate to Severe. The defaults of 0.0 and 0 are NOT sensible - they should be `None` or use averages.

### 5.3 Vulnerability Data Unavailable

**What happens:**
- `vulnerabilities` list is empty
- Security score: 100.0 (perfect)

**This is DANGEROUS:** If OSV is down, all packages get 100% security score, which is a false positive. There should be a "security data unavailable" flag that affects confidence, not score.

### 5.4 pypistats.org Unavailable

**What happens:**
- `get_download_stats()` returns 0
- `downloads_last_month` stays at 0
- Popularity score tanks

**Default Applied:** 0 (not sensible - should be None or use cached/estimated value)

---

## 6. Summary of Identified Problems

### Critical Bugs

1. **Download data always 0** unless separate API call made (and succeeds)
2. **Code quality score computed but unused**
3. **Community score base of 0** (should be 50 like others)
4. **Popularity score base of 0** (should be 50 like others)

### Design Flaws

1. **Stars counted twice** (community + popularity)
2. **Stable packages penalized** for low commit frequency
3. **Rate-limited GitHub defaults to 0** instead of neutral values
4. **No "data unavailable" confidence indication**
5. **Vulnerability absence = perfect score** (false positive risk)
6. **Grade thresholds too harsh** given scoring biases

### Missing Features

1. License scoring
2. Python version compatibility
3. Documentation assessment
4. Test coverage
5. CI/CD status
6. Typosquatting detection
7. Transitive dependency count

### Threshold Recommendations

Current thresholds assume a well-balanced scoring system. Given the identified biases, either:

**Option A - Fix the scoring (recommended):**
- Fix download data bug
- Change community/popularity base to 50
- Remove double-counting of stars
- Add "data confidence" indicator

**Option B - Adjust thresholds (band-aid):**
| Grade | Current | Adjusted |
|-------|---------|----------|
| A     | 90+     | 85+      |
| B     | 80-89   | 72-84    |
| C     | 70-79   | 60-71    |
| D     | 60-69   | 45-59    |
| F     | <60     | <45      |

---

## 7. Recommendations

### Immediate Fixes (High Priority)

1. **Fix download data collection:**
   - Call `get_download_stats()` as part of the standard PyPI data collection
   - Cache results to avoid repeated calls
   - Add fallback estimation based on PyPI ranking if pypistats unavailable

2. **Use code quality score or remove it:**
   ```python
   overall = (
       security * self.weights["security"]
       + maintenance * self.weights["maintenance"]
       + community * self.weights["community"]
       + popularity * self.weights["popularity"]
       + code_quality * self.weights.get("quality", 0)  # Add weight
   )
   ```

3. **Change community score base to 50:**
   ```python
   def _calculate_community_score(self, repo):
       if not repo:
           return 50.0

       score = 50.0  # Changed from 0.0
       # Then reduce point values proportionally
   ```

4. **Change popularity score base to 50:**
   ```python
   def _calculate_popularity_score(self, pypi, repo):
       score = 50.0  # Changed from 0.0
       # Then reduce point values proportionally
   ```

### Medium Priority Fixes

5. **Handle rate-limited GitHub gracefully:**
   - Return `None` for metrics, not 0
   - In calculator, treat `None` as "unknown" with neutral impact

6. **Remove star double-counting:**
   - Remove star bonus from popularity score (keep it in community only)

7. **Add "stable package" heuristic:**
   - If package has 20+ releases AND release_date > 1 year AND no vulnerabilities, consider it "stable mature" not "unmaintained"

8. **Add data confidence score:**
   ```python
   confidence = 1.0
   if not pypi:
       confidence *= 0.7
   if not repo:
       confidence *= 0.8
   if not vulnerabilities_checked:  # Add this flag
       confidence *= 0.5
   ```

### Long-term Improvements

9. **Add license scoring** (OSI-approved, permissive, copyleft, unknown)
10. **Add Python version support scoring** (supports latest Python = bonus)
11. **Integrate with CI status** (GitHub Actions badges, etc.)
12. **Add dependency depth penalty** (packages that bring 50+ transitive deps)

---

## Appendix: Score Calculation Flowchart

```
                    +------------------+
                    |  Input Data      |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
  +------+------+    +-------+-------+   +-------+-------+
  | PyPI Data   |    | GitHub Data   |   | OSV Data      |
  | - version   |    | - stars       |   | - vulns       |
  | - release   |    | - contributors|   | - severity    |
  | - downloads*|    | - commits     |   +-------+-------+
  +------+------+    | - issues      |           |
         |           +-------+-------+           |
         |                   |                   |
         v                   v                   v
  +------+------+    +-------+-------+   +-------+-------+
  | Maintenance |    | Community     |   | Security      |
  | Base: 50    |    | Base: 0 !!!   |   | Base: 100     |
  | Max: 100    |    | Max: 100      |   | Min: 0        |
  +------+------+    +-------+-------+   +-------+-------+
         |                   |                   |
         |           +-------+-------+           |
         |           | Popularity    |           |
         |           | Base: 0 !!!   |           |
         |           | Max: 100      |           |
         |           +-------+-------+           |
         |                   |                   |
         +-------------------+-------------------+
                             |
                             v
                    +--------+---------+
                    | Weighted Sum     |
                    | Sec: 35%         |
                    | Mnt: 30%         |
                    | Com: 20%         |
                    | Pop: 15%         |
                    +--------+---------+
                             |
                             v
                    +--------+---------+
                    | Grade Mapping    |
                    | A: 90+           |
                    | B: 80-89         |
                    | C: 70-79         |
                    | D: 60-69         |
                    | F: <60           |
                    +------------------+

* downloads_last_month defaults to 0 due to bug
```

---

*End of Analysis*
