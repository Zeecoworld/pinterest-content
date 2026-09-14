import calendar as cal_module
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AutomationSettingsForm, BoardForm, ContentCategoryForm, PinContentForm
from .models import AutomationSettings, Board, ContentCategory, PinContent, PostLog


@login_required
def dashboard(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    qs = PinContent.objects.select_related("board", "category")

    stats = {
        "total": qs.count(),
        "posted": qs.filter(status=PinContent.Status.POSTED).count(),
        "scheduled": qs.filter(status=PinContent.Status.SCHEDULED).count(),
        "drafts": qs.filter(status=PinContent.Status.DRAFT).count(),
        "posted_this_week": qs.filter(
            status=PinContent.Status.POSTED, posted_at__date__gte=week_start
        ).count(),
        "failed": qs.filter(status=PinContent.Status.FAILED).count(),
    }

    activity = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = qs.filter(status=PinContent.Status.POSTED, posted_at__date=day).count()
        activity.append({"label": day.strftime("%a"), "count": count})

    upcoming = qs.filter(
        status=PinContent.Status.SCHEDULED, scheduled_for__gte=timezone.now()
    ).order_by("scheduled_for")[:6]

    recent = qs.order_by("-created_at")[:6]

    category_breakdown = (
        ContentCategory.objects.annotate(pin_count=Count("pins"))
        .filter(pin_count__gt=0)
        .order_by("-pin_count")[:6]
    )

    automation = AutomationSettings.load()
    recent_logs = PostLog.objects.select_related("pin")[:5]

    context = {
        "stats": stats,
        "activity": activity,
        "max_activity": max([a["count"] for a in activity] + [1]),
        "upcoming": upcoming,
        "recent": recent,
        "category_breakdown": category_breakdown,
        "automation": automation,
        "recent_logs": recent_logs,
        "boards_count": Board.objects.filter(is_active=True).count(),
    }
    return render(request, "pins/dashboard.html", context)


@login_required
def content_list(request):
    qs = PinContent.objects.select_related("board", "category")

    status = request.GET.get("status")
    category_slug = request.GET.get("category")
    board_id = request.GET.get("board")
    query = request.GET.get("q")

    if status:
        qs = qs.filter(status=status)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if board_id:
        qs = qs.filter(board_id=board_id)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))

    context = {
        "pins": qs,
        "statuses": PinContent.Status.choices,
        "categories": ContentCategory.objects.all(),
        "boards": Board.objects.filter(is_active=True),
        "active_status": status or "",
        "active_category": category_slug or "",
        "active_board": board_id or "",
        "query": query or "",
    }
    return render(request, "pins/content_list.html", context)


@login_required
def content_create(request):
    if request.method == "POST":
        form = PinContentForm(request.POST, request.FILES)
        if form.is_valid():
            pin = form.save()
            messages.success(request, f'"{pin.title}" saved successfully.')
            return redirect("pins:content_list")
    else:
        form = PinContentForm(initial={"status": PinContent.Status.DRAFT})
    return render(request, "pins/content_form.html", {"form": form, "is_edit": False})


@login_required
def content_edit(request, pk):
    pin = get_object_or_404(PinContent, pk=pk)
    if request.method == "POST":
        form = PinContentForm(request.POST, request.FILES, instance=pin)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{pin.title}" updated.')
            return redirect("pins:content_list")
    else:
        form = PinContentForm(instance=pin)
    return render(request, "pins/content_form.html", {"form": form, "is_edit": True, "pin": pin})


@login_required
def content_delete(request, pk):
    pin = get_object_or_404(PinContent, pk=pk)
    if request.method == "POST":
        title = pin.title
        pin.delete()
        messages.success(request, f'"{title}" deleted.')
        return redirect("pins:content_list")
    return render(request, "pins/content_confirm_delete.html", {"pin": pin})


@login_required
def content_detail(request, pk):
    pin = get_object_or_404(PinContent.objects.select_related("board", "category"), pk=pk)
    return render(request, "pins/content_detail.html", {"pin": pin})


@login_required
def calendar_view(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    cal = cal_module.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    pins = PinContent.objects.filter(
        Q(scheduled_for__year=year, scheduled_for__month=month)
        | Q(posted_at__year=year, posted_at__month=month)
    ).select_related("board", "category")

    pins_by_day = {}
    for pin in pins:
        relevant_dt = pin.posted_at or pin.scheduled_for
        if relevant_dt:
            day_key = timezone.localtime(relevant_dt).date()
            pins_by_day.setdefault(day_key, []).append(pin)

    weeks = []
    for week in month_days:
        week_data = []
        for day in week:
            week_data.append(
                {
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "pins": pins_by_day.get(day, []),
                }
            )
        weeks.append(week_data)

    prev_month = (date(year, month, 1) - timedelta(days=1)).replace(day=1)
    next_month = (date(year, month, 28) + timedelta(days=7)).replace(day=1)

    context = {
        "weeks": weeks,
        "month_name": date(year, month, 1).strftime("%B %Y"),
        "prev_year": prev_month.year,
        "prev_month": prev_month.month,
        "next_year": next_month.year,
        "next_month": next_month.month,
    }
    return render(request, "pins/calendar.html", context)


@login_required
def boards_list(request):
    boards = Board.objects.annotate(pin_count=Count("pins")).order_by("name")
    if request.method == "POST":
        form = BoardForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Board added.")
            return redirect("pins:boards_list")
    else:
        form = BoardForm()
    return render(request, "pins/boards.html", {"boards": boards, "form": form})


@login_required
def categories_list(request):
    categories = ContentCategory.objects.annotate(pin_count=Count("pins")).order_by("name")
    if request.method == "POST":
        form = ContentCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category added.")
            return redirect("pins:categories_list")
    else:
        form = ContentCategoryForm()
    return render(request, "pins/categories.html", {"categories": categories, "form": form})


@login_required
def automation_settings(request):
    settings_obj = AutomationSettings.load()
    if request.method == "POST":
        form = AutomationSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            if not form.cleaned_data.get("pinterest_access_token"):
                form.instance.pinterest_access_token = settings_obj.pinterest_access_token
            form.save()
            messages.success(request, "Automation settings saved.")
            return redirect("pins:automation_settings")
    else:
        form = AutomationSettingsForm(instance=settings_obj)

    logs = PostLog.objects.select_related("pin")[:15]
    return render(
        request,
        "pins/settings.html",
        {"form": form, "settings": settings_obj, "logs": logs},
    )
