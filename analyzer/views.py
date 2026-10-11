
# ابزارهای موردنیاز برای پردازش درخواست‌ها و تحلیل کد Python

import ast
import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods


# مسیر فایل اجرایی Ruff
RUFF_PATH = Path(settings.BASE_DIR) / "tools" / "ruff.exe"


def explain_issue(code, message=""):
    """توضیح فارسی و ارائه راهکار برای مشکلات شناسایی‌شده."""

    explanations = {
        "F401": (
            "ماژول یا نامی وارد شده، اما در کد استفاده نشده است.",
            "اگر به آن نیاز نداری، دستور import مربوطه را حذف کن."
        ),
        "F841": (
            "یک متغیر مقداردهی شده، اما مقدار آن استفاده نشده است.",
            "اگر متغیر لازم نیست، آن را حذف کن؛ در غیر این صورت "
            "بررسی کن که آیا استفاده از آن را فراموش کرده‌ای."
        ),
        "F821": (
            "نام یک متغیر یا شناسه تعریف نشده است.",
            "املای نام را بررسی کن و مطمئن شو قبل از استفاده تعریف شده است."
        ),
        "F541": (
            "از f-string استفاده شده، اما جای‌گذاری متغیر ندارد.",
            "اگر به قالب‌بندی رشته نیاز نداری، حرف f را حذف کن."
        ),
        "E722": (
            "از except عمومی استفاده شده و نوع استثنا مشخص نیست.",
            "نوع استثنای مورد انتظار را مشخص کن؛ برای مثال "
            "از except ValueError استفاده کن، اگر مناسب است."
        ),
        "E711": (
            "مقایسه با None به شکل مناسبی انجام نشده است.",
            "برای بررسی نبودن مقدار از is None یا is not None استفاده کن."
        ),
        "E712": (
            "مقایسه با True یا False به شکل مناسبی نوشته نشده است.",
            "شرط را ساده‌تر بنویس؛ مثلاً if active: به‌جای "
            "if active == True:."
        ),
        "E501": (
            "طول خط از حد مجاز انتخاب‌شده بیشتر است.",
            "در صورت امکان، دستور را به چند خط کوتاه‌تر تقسیم کن."
        ),
        "F811": (
            "یک نام ممکن است چند بار تعریف شده باشد.",
            "تعریف‌های تکراری را بررسی کن و در صورت نیاز اصلاح کن."
        ),
        "F823": (
            "یک متغیر محلی پیش از مقداردهی استفاده شده است.",
            "مطمئن شو متغیر پیش از استفاده مقداردهی می‌شود."
        ),
        "AST-SYNTAX": (
            "ساختار نحوی کد پایتون معتبر نیست.",
            "شماره خط و پیام خطا را بررسی کن؛ ممکن است پرانتز، "
            "دونقطه یا علامت نقل‌قول جا افتاده باشد."
        ),
    }

    if code in explanations:
        explanation, suggestion = explanations[code]
    else:
        explanation = (
            f"مشکلی با کد {code or 'نامشخص'} شناسایی شده است. "
            f"جزئیات ابزار: {message}"
        )
        suggestion = (
            "پیام اصلی خطا و شماره خط را بررسی کن و کد مربوطه را اصلاح کن."
        )

    return {
        "explanation": explanation,
        "suggestion": suggestion,
    }


def classify_issue(issue):
    """تعیین دسته و شدت مشکل."""

    code = issue.get("code") or ""

    if code in {"AST-SYNTAX", "E999"}:
        category = "syntax"
        category_fa = "خطای نحوی"
        severity = "critical"
        severity_fa = "بحرانی"
        weight = 30

    elif code in {"F821", "F823"}:
        category = "bug"
        category_fa = "باگ احتمالی"
        severity = "high"
        severity_fa = "زیاد"
        weight = 12

    elif code.startswith("F"):
        category = "quality"
        category_fa = "کیفیت و صحت کد"
        severity = "medium"
        severity_fa = "متوسط"
        weight = 5

    elif code.startswith("E"):
        category = "style"
        category_fa = "استاندارد کدنویسی"
        severity = "low"
        severity_fa = "کم"
        weight = 2

    elif code.startswith("W"):
        category = "warning"
        category_fa = "هشدار"
        severity = "low"
        severity_fa = "کم"
        weight = 2

    else:
        category = "other"
        category_fa = "سایر موارد"
        severity = "low"
        severity_fa = "کم"
        weight = 2

    return {
        "category": category,
        "category_fa": category_fa,
        "severity": severity,
        "severity_fa": severity_fa,
        "weight": weight,
    }


def calculate_quality_score(issues, syntax_valid=True):
    """محاسبه امتیاز تخمینی کیفیت کد از ۱۰۰."""

    score = 100

    category_counts = {
        "syntax": 0,
        "bug": 0,
        "quality": 0,
        "style": 0,
        "warning": 0,
        "other": 0,
    }

    severity_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    for issue in issues:
        classification = classify_issue(issue)
        issue.update(classification)

        category_counts[classification["category"]] += 1
        severity_counts[classification["severity"]] += 1
        score -= classification["weight"]

    # اگر نحو کد نامعتبر باشد، امتیاز حداکثر ۲۰ خواهد بود.
    if not syntax_valid:
        score = min(score, 20)

    score = max(0, min(100, score))

    if score >= 90:
        grade = "عالی"
        description = "در بررسی‌های انجام‌شده مشکلات کمی شناسایی شده‌اند."
    elif score >= 75:
        grade = "خوب"
        description = "کد وضعیت مناسبی دارد، اما جای بهبود وجود دارد."
    elif score >= 50:
        grade = "متوسط"
        description = "چند مشکل وجود دارد که بهتر است اصلاح شوند."
    elif score >= 25:
        grade = "ضعیف"
        description = "کد به بازبینی و اصلاح قابل‌توجهی نیاز دارد."
    else:
        grade = "نیازمند اصلاح جدی"
        description = "ابتدا مشکلات اساسی کد را برطرف کن."

    return {
        "score": score,
        "grade": grade,
        "description": description,
        "category_counts": category_counts,
        "severity_counts": severity_counts,
    }


def analyze_with_ast(code):
    """استخراج آمار ساختاری و بررسی نحو کد با AST."""

    stats = {
        "line_count": len(code.splitlines()),
        "function_count": 0,
        "class_count": 0,
        "import_count": 0,
        "syntax_valid": True,
    }

    try:
        tree = ast.parse(code)

    except SyntaxError as error:
        stats["syntax_valid"] = False

        issue = {
            "code": "AST-SYNTAX",
            "message": error.msg,
            "row": error.lineno,
            "column": error.offset,
        }

        issue.update(explain_issue(issue["code"], issue["message"]))

        return stats, [issue]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stats["function_count"] += 1

        elif isinstance(node, ast.ClassDef):
            stats["class_count"] += 1

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            stats["import_count"] += 1

    return stats, []


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def analyze_code(request):
    """نمایش صفحه یا تحلیل کد ارسالی از رابط کاربری."""

    if request.method == "GET":
        return render(request, "analyzer/index.html")

    # دریافت و اعتبارسنجی JSON
    try:
        data = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "درخواست JSON معتبر نیست."},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "ساختار درخواست معتبر نیست."},
            status=400,
        )

    code = data.get("code", "")

    if not isinstance(code, str) or not code.strip():
        return JsonResponse(
            {"error": "لطفاً کد Python را وارد کنید."},
            status=400,
        )

    if len(code) > 50_000:
        return JsonResponse(
            {"error": "حجم کد نباید بیشتر از ۵۰ هزار کاراکتر باشد."},
            status=400,
        )

    # بررسی وجود Ruff
    if not RUFF_PATH.is_file():
        return JsonResponse(
            {"error": "فایل اجرایی Ruff پیدا نشد."},
            status=500,
        )

    # اجرای Ruff
    try:
        result = subprocess.run(
            [
                str(RUFF_PATH),
                "check",
                "--output-format",
                "json",
                "--stdin-filename",
                "submitted_code.py",
                "-",
            ],
            input=code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            cwd=str(settings.BASE_DIR),
        )

    except subprocess.TimeoutExpired:
        return JsonResponse(
            {"error": "تحلیل کد بیش از حد طول کشید."},
            status=408,
        )

    except OSError:
        return JsonResponse(
            {"error": "اجرای تحلیل‌گر با خطا مواجه شد."},
            status=500,
        )

    if result.returncode not in (0, 1):
        return JsonResponse(
            {"error": "اجرای تحلیل‌گر با خطا مواجه شد."},
            status=500,
        )

    # پردازش گزارش Ruff
    try:
        issues = json.loads(result.stdout)

    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "پاسخ تحلیل‌گر قابل پردازش نیست."},
            status=500,
        )

    if not isinstance(issues, list):
        return JsonResponse(
            {"error": "ساختار گزارش تحلیل‌گر معتبر نیست."},
            status=500,
        )

    # اضافه‌کردن توضیحات فارسی به خطاهای Ruff
    for issue in issues:
        if isinstance(issue, dict):
            issue.update(
                explain_issue(
                    issue.get("code"),
                    issue.get("message", ""),
                )
            )

    # تحلیل ساختار کد
    stats, syntax_issues = analyze_with_ast(code)

    # ادغام خطاهای نحوی AST با گزارش Ruff
    issues.extend(syntax_issues)

    # امتیازدهی و دسته‌بندی خطاها
    quality = calculate_quality_score(
        issues,
        syntax_valid=stats["syntax_valid"],
    )

    # خلاصه گزارش
    if not issues:
        summary = "ایرادی توسط بررسی‌های فعلی پیدا نشد."
    else:
        summary = f"{len(issues)} مورد برای بررسی پیدا شد."

    # ارسال گزارش نهایی
    return JsonResponse(
        {
            "issues": issues,
            "issue_count": len(issues),
            "summary": summary,
            "stats": stats,
            "quality": quality,
        }
    )
