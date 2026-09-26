from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path("/Users/tomatocoder/Desktop/moscow-transport-hackathon/docs/img")
INK, MUTED, BORDER, BG = "#1f2426", "#5f686c", "#737b7f", "#f5f5f5"
WRITE, READ = "#b3302a", "#2c6a6e"
FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"


class Svg:
    def __init__(self, width: int, height: int, title: str):
        self.w, self.h = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" font-family="{FONT}">',
            "<defs>",
            *(
                f'<marker id="a-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
                for name, color in (("w", WRITE), ("r", READ), ("m", MUTED))
            ),
            "</defs>",
            f'<rect width="{width}" height="{height}" fill="{BG}"/>',
            f'<text x="{width / 2}" y="44" text-anchor="middle" font-size="22" font-weight="600" fill="{INK}">{escape(title)}</text>',
        ]

    def band(self, y: int, h: int, label: str, fill: str):
        self.parts.append(f'<rect x="16" y="{y}" width="{self.w - 32}" height="{h}" rx="12" fill="{fill}"/>')
        self.parts.append(
            f'<text x="34" y="{y + 26}" font-size="13" font-weight="700" letter-spacing="1" fill="{MUTED}">{escape(label)}</text>'
        )

    def box(self, x: int, y: int, w: int, h: int, title: str, lines: list[str] = (), dashed: bool = False, stroke: str = BORDER, fill: str = "#ffffff", title_size: int = 15):
        dash = ' stroke-dasharray="7 5"' if dashed else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>')
        self.parts.append(f'<text x="{x + 14}" y="{y + 26}" font-size="{title_size}" font-weight="600" fill="{INK}">{escape(title)}</text>')
        for i, line in enumerate(lines):
            self.parts.append(f'<text x="{x + 14}" y="{y + 48 + 18 * i}" font-size="12.5" fill="{MUTED}">{escape(line)}</text>')

    def text(self, x: float, y: float, value: str, color: str = MUTED, size: float = 12, anchor: str = "start", weight: int = 400):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>')

    def arrow(self, path: str, kind: str = "m", both: bool = False, dashed: bool = False):
        color = {"w": WRITE, "r": READ, "m": MUTED}[kind]
        start = f' marker-start="url(#a-{kind})"' if both else ""
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="url(#a-{kind})"{start}/>')

    def save(self, name: str):
        (OUT / name).write_text("\n".join([*self.parts, "</svg>"]), encoding="utf-8")


def docker_diagram():
    s = Svg(1400, 900, "Логика Docker: контейнеры и общий том")

    s.box(40, 90, 300, 62, "Источник выгрузок", ["CSV валидаций, настраивают инженеры"], dashed=True)
    s.box(40, 170, 300, 62, "./dataset (только чтение)", ["история для начальной загрузки"], dashed=True, title_size=13)
    s.box(40, 250, 300, 190, "ingest", [
        "образ tram-forecast/ingest · 172 МБ",
        "лимит: 1 CPU · 2 ГБ",
        "python -m mtml.ingest run",
        "опрос inbox/ раз в 60 с",
        "разбор → сырой слой → факты",
        "→ статусы дней → водяной знак",
    ], stroke=WRITE)
    s.box(40, 500, 300, 210, "ml-worker", [
        "образ tram-forecast/ml-worker · 428 МБ",
        "torch CPU · лимит: 2 CPU · 3 ГБ",
        "python -m mtml.worker run",
        "пересчёт: сдвиг водяного знака",
        "или ночь 03:00 (не чаще раза в 60 мин)",
        "краткосрочный 61 д + эффекты",
        "+ годовой + мониторинг точности",
    ], stroke=WRITE)
    s.box(40, 760, 300, 58, "Hugging Face", ["веса Chronos-2, скачиваются один раз"], dashed=True, title_size=13)

    s.box(470, 80, 450, 700, "Том tram-data  (/data)", [], dashed=True, stroke=READ, fill="#eef4f4", title_size=17)
    s.box(492, 128, 406, 196, "пишет ingest", [
        "inbox/  ← новые CSV, processed/, failed/",
        "raw/validations/  посадки по дням",
        "actuals/actuals_hourly.parquet  факт маршрут × час",
        "actuals/day_status.parquet  final / partial / missing",
        "ingestion/  журнал загрузок, карантин",
        "state/watermark.json  до какой даты данные полные",
        "tmp/duckdb/  сброс памяти при больших файлах",
    ], fill="#fbeeed", stroke=WRITE, title_size=14)
    s.box(492, 346, 406, 196, "пишет ml-worker", [
        "runs/<run_id>/forecasts.parquet  прогноз",
        "runs/<run_id>/effects.parquet  эффекты для слайдеров",
        "runs/<run_id>/meta.json  модель, данные, проверки",
        "active.json  какие прогоны актуальны",
        "monitoring/accuracy.parquet  реальная точность",
        "state/worker.json  последний прогон, ошибка",
        "hf/  кэш весов Chronos-2",
    ], fill="#fbeeed", stroke=WRITE, title_size=14)
    s.box(492, 564, 406, 88, "общее для всех сервисов", [
        "state/clock.json  «сейчас» системы",
        "(в демо — 01.11.2025 03:00; системное время не использовать)",
    ], fill="#ffffff", title_size=14)
    s.text(695, 700, "бэкенд подключает том только на чтение (:ro)", color=READ, size=12.5, anchor="middle", weight=600)

    s.box(1050, 90, 310, 70, "БД бэкенда", ["сценарии и поправки диспетчера"], dashed=True, title_size=14)
    s.box(1050, 250, 310, 200, "backend", [
        "команда бэкенда · FastAPI",
        "том только на чтение",
        "держит прогноз в памяти,",
        "перечитывает active.json раз в 30 с",
        "склейка: факт → short → year",
        "поправки, API, экспорт CSV / XLSX",
    ], stroke=READ)
    s.box(1050, 530, 310, 150, "frontend", [
        "команда фронтенда",
        "только HTTP к backend",
        "сутки и неделя по часам,",
        "месяц и год по дням, карта, слайдеры",
    ])
    s.box(1050, 760, 310, 58, "Диспетчер", ["браузер"], dashed=True, title_size=14)

    s.arrow("M340,121 C 410,121 420,160 492,160")
    s.text(350, 112, "CSV → inbox/")
    s.arrow("M190,232 V250")
    s.arrow("M340,300 H492", "w", both=True)
    s.text(350, 292, "чтение и запись", color=WRITE)
    s.arrow("M492,250 C 420,250 420,520 340,520", "r")
    s.text(60, 474, "читает факты, статусы и водяной знак", color=READ)
    s.arrow("M340,560 C 420,560 420,445 492,445", "w")
    s.text(350, 590, "пишет прогнозы", color=WRITE)
    s.arrow("M190,760 V710")
    s.arrow("M920,350 H1050", "r")
    s.text(930, 342, "только чтение", color=READ)
    s.arrow("M1205,160 V250", both=True)
    s.arrow("M1205,450 V530", both=True)
    s.text(1215, 495, "HTTP API")
    s.arrow("M1205,680 V760", both=True)
    s.save("docker-architecture.svg")


def pipeline_diagram():
    s = Svg(1480, 1080, "Пайплайн: от прихода данных до бэкенда и фронтенда")
    xs = [200, 450, 700, 950, 1200]
    bw = 230

    s.band(64, 110, "ПРИХОД", "#ececec")
    s.box(xs[0], 82, bw, 74, "Источник выгрузок", ["CSV валидаций", "настраивают инженеры"], dashed=True)
    s.box(xs[1], 82, bw, 74, "inbox/*.csv", ["файл кладётся как .part", "и переименовывается в .csv"])
    s.box(xs[4], 82, bw, 74, "state/clock.json", ["«сейчас» для всех сервисов", "в демо: 01.11.2025 03:00"], dashed=True)
    s.arrow(f"M{xs[0] + bw},119 H{xs[1]}")

    s.band(196, 140, "INGEST", "#fbeeed")
    ingest = [
        ("Разбор", ["заголовок, типы (TRY_CAST)", "отказы → только счёт", "битые строки → карантин"]),
        ("Сырой слой", ["файл на каждый день", "без дублей по ключу", "(device, tran_no, время)"]),
        ("Факты", ["маршрут × час", "затронутые дни", "пересчитываются целиком"]),
        ("Статусы дней", ["final / partial / missing", "по возрасту дня", "+ флаг anomaly (ремонт)"]),
        ("Водяной знак", ["последний полный день", "state/watermark.json"]),
    ]
    for x, (title, lines) in zip(xs, ingest, strict=True):
        s.box(x, 222, bw, 98, title, lines, stroke=WRITE)
    for a, b in zip(xs, xs[1:]):
        s.arrow(f"M{a + bw},271 H{b}", "w")
    s.arrow(f"M{xs[1] + bw / 2},156 V222", "w")
    s.arrow(f"M{xs[4] + bw / 2},156 V222", dashed=True)
    s.text(xs[4] + bw / 2 + 8, 196, "возраст дня")

    s.band(358, 330, "ML-WORKER", "#e8f1f1")
    worker = [
        ("Расписание", ["знак сдвинулся или ночь 03:00", "не чаще MIN_RERUN_MINUTES", "state/worker.json"]),
        ("Контекст", ["история до водяного знака", "плотная сетка маршрут × час", "cold start → 0"]),
        ("Краткосрочный", ["ансамбль RH + RHD + V2", "61 день почасово", "календарь, каникулы, тип дня"]),
        ("Эффекты", ["контрольные прогоны без", "праздников и без каникул", "→ effects.parquet"]),
        ("Проверки → публикация", ["сетка, NaN, недельные суммы", "runs/<id>/ → active.json", "плохой прогноз не публикуется"]),
    ]
    for x, (title, lines) in zip(xs, worker, strict=True):
        s.box(x, 384, bw, 98, title, lines, stroke=READ)
    for a, b in zip(xs, xs[1:]):
        s.arrow(f"M{a + bw},433 H{b}", "r")
    s.box(xs[2], 512, bw, 84, "Годовой", ["сезонная модель, 365 дней", "месяц × тип дня × каникулы"], stroke=READ)
    s.box(xs[0], 512, bw, 122, "Входы моделей", ["календарь 2025–26, каникулы", "(зашиты в образ)", "веса Chronos-2: Hugging Face", "→ кэш /data/hf"], dashed=True, title_size=14)
    s.box(xs[4], 598, bw, 72, "Мониторинг", ["прогнозы против фактов", "monitoring/accuracy.parquet"], stroke=READ)
    s.arrow(f"M{xs[1] + bw / 2},482 V554 H{xs[2]}", "r")
    s.arrow(f"M{xs[2] + bw},554 H{xs[4] + bw / 2 - 30} V482", "r")
    s.arrow(f"M{xs[0] + bw},530 C {xs[1] + 120},530 {xs[2] - 20},510 {xs[2] + 40},482", dashed=True)
    s.arrow(f"M{xs[0] + bw},590 H{xs[2]}", dashed=True)
    s.arrow(f"M{xs[4] + bw / 2 + 40},482 V598", "r")
    s.text(xs[4] + bw / 2 + 48, 548, "факты пришли", color=READ)
    s.arrow(f"M{xs[4] + bw / 2},320 V340 H{xs[0] + bw / 2} V384", "r")
    s.text(xs[1] + 20, 336, "водяной знак сдвинулся", color=READ)
    s.arrow(f"M{xs[2] + bw / 2},320 V350 H{xs[1] + bw / 2} V384", "r")
    s.text(xs[1] + bw / 2 + 8, 366, "факты и статусы", color=READ)

    s.band(706, 170, "BACKEND", "#f0ecf6")
    backend = [
        ("Чтение тома", ["active.json раз в 30 с,", "прогноз и эффекты в памяти"]),
        ("Склейка", ["факт до водяного знака,", "short до 61 дня, дальше year"]),
        ("Поправки", ["effects × k (слайдеры),", "сценарии × m"]),
        ("API и экспорт", ["маршрут, остановка, интервал,", "горизонт; CSV / XLSX"]),
        ("БД бэкенда", ["сценарии и поправки", "диспетчера"]),
    ]
    for x, (title, lines) in zip(xs, backend, strict=True):
        s.box(x, 736, bw, 84, title, lines, dashed=title == "БД бэкенда")
    for a, b in zip(xs[:3], xs[1:4]):
        s.arrow(f"M{a + bw},778 H{b}")
    s.arrow(f"M{xs[4]},778 H{xs[3] + bw}", both=True)
    s.arrow(f"M{xs[4] + bw},433 H{xs[4] + bw + 22} V718 H{xs[0] + bw / 2} V736", "r")
    s.text(xs[1] + 20, 712, "active.json → новый прогноз (том только на чтение)", color=READ)

    s.band(894, 164, "FRONTEND", "#fbf4e4")
    front = [
        ("Сутки", ["по часам"]),
        ("Неделя", ["по дням и часам"]),
        ("Месяц и год", ["по дням, неделям, месяцам"]),
        ("Поправки и события", ["слайдеры, форма события"]),
        ("Карта и экспорт", ["остановки, CSV / XLSX"]),
    ]
    for x, (title, lines) in zip(xs, front, strict=True):
        s.box(x, 930, bw, 70, title, lines)
    s.arrow(f"M{xs[3] + bw / 2},820 V930", both=True)
    s.text(xs[3] + bw / 2 + 8, 880, "HTTP API")
    s.save("pipeline.svg")


def ensemble_diagram():
    s = Svg(1480, 1120, "Боевая модель: ensemble_cal_school_daytype_profile")
    xs, bw = [40, 278, 516, 754, 992, 1230], 216

    s.band(64, 146, "ВХОДЫ", "#ececec")
    inputs = [
        ("Факты (actuals)", ["история до водяного знака", "плотная сетка маршрут × час", "из ingest"], False),
        ("calendar.csv · isDayOff", ["is_non_working", "is_holiday_weekday", "is_shortened · 2025–2026"], False),
        ("Школьные каникулы", ["school_holiday_modular", "school_holiday_quarter", "источники в CSV"], False),
        ("Тип дня (covariates.py)", ["workday / saturday / sunday", "holiday / pre_holiday /", "post_holiday"], False),
        ("Chronos-2 (Hugging Face)", ["amazon/chronos-2, zero-shot", "без дообучения", "одна копия весов"], False),
        ("Погода (не входит)", ["только эксперименты", "_wx / _pwx", "прирост ≤ +0.0007"], True),
    ]
    for x, (title, lines, dashed) in zip(xs, inputs, strict=True):
        s.box(x, 92, bw, 104, title, lines, dashed=dashed, title_size=14)

    s.band(226, 560, "УЧАСТНИКИ АНСАМБЛЯ · каждый получает историю, свою часть ковариат и общие веса", "#e8f1f1")
    chronos_lines = [
        "Chronos2Forecaster, route_hour_daily",
        "216 рядов = 9 маршрутов × 24 часа",
        "ряд: посадки в этот час по дням",
        "горизонт 61 шаг (день)",
        "",
        "ковариаты на горизонте:",
        "· is_non_working",
        "· is_holiday_weekday",
        "· is_shortened",
        "· school_holiday_modular",
        "· school_holiday_quarter",
    ]
    s.box(40, 262, 300, 506, "RH · вес 1/3", [
        *chronos_lines, "", "", "", "выход: медиана, q10, q90", "= chronos2_daily_cal_school",
    ], stroke=READ, title_size=16)
    s.box(360, 262, 300, 506, "RHD · вес 1/3", [
        *chronos_lines, "· day_type", "", "", "выход: медиана, q10, q90",
        "= chronos2_daily_cal_school_daytype", "(прежняя боевая модель)",
    ], stroke=READ, title_size=16)

    s.box(680, 262, 764, 506, "V2 · ProfileDailyForecaster · вес 1/3", [], stroke=MUTED, fill="#f7fafa", title_size=16)
    s.box(700, 306, 724, 66, "day_features: признаки дня из календаря", [
        "dow · work_weekend (рабочая Сб/Вс) · special = праздник в будни или рабочий выходной",
    ], title_size=13)
    vx, vw = [700, 947, 1194], 230
    s.box(vx[0], 392, vw, 156, "Недельный профиль (без ML)", [
        "уровень: медиана Пн–Чт за 7 дн", "× коэф. дня недели за 6 нед", "доли часов: за 4 недели",
        "праздник → как воскресенье", "раб. суббота → (Пт + Сб) / 2",
    ], title_size=13)
    s.box(vx[1], 392, vw, 156, "Chronos-2: суммы за день", [
        "10 рядов — по маршруту", "горизонт 61 день", "ковариат нет", "медиана",
    ], stroke=READ, title_size=13)
    s.box(vx[2], 392, vw, 156, "Chronos-2: суммы + календарь", [
        "10 рядов — по маршруту", "на горизонте:", "is_non_working,", "is_holiday_weekday, dow", "медиана",
    ], stroke=READ, title_size=13)
    for x in vx:
        s.arrow(f"M{x + vw / 2},372 V392")
    s.box(vx[1], 572, 477, 84, "spread_over_hours: сумма дня → по часам", [
        "сумма дня × доли часов профиля;",
        "в special-дни и при простое маршрута (< 5%) — сумма профиля",
    ], title_size=13)
    s.arrow(f"M{vx[1] + vw / 2},548 V572")
    s.arrow(f"M{vx[2] + vw / 2},548 V572")
    s.arrow(f"M{vx[0] + vw - 20},548 V600 H{vx[1]}", dashed=True)
    s.text(vx[0] + vw - 26, 596, "форма", anchor="end")
    s.box(700, 680, 724, 72, "Среднее трёх вариантов → × new_year_factor", [
        "будни 27–31.12 × ≈ 0.90: первые рабочие дни последнего января к трём следующим неделям",
    ], title_size=13)
    s.arrow(f"M{vx[0] + 60},548 V680")
    s.arrow(f"M{vx[1] + 240},656 V680")

    s.band(800, 160, "ENSEMBLEFORECASTER", "#fbeeed")
    s.box(40, 842, 900, 100, "yhat = (RH + RHD + V2) / 3", [
        "q10, q90 = среднее по RH и RHD (у V2 квантилей нет)",
        "одна таблица ковариат на всех: подмена covariates доходит до каждого участника",
    ], stroke=WRITE, title_size=16)
    s.box(960, 842, 484, 100, "Итоговые веса", [
        "RH 1/3 · RHD 1/3",
        "профиль 1/9 · суммы без ковариат 1/9 · суммы + календарь 1/9",
    ], title_size=14)
    s.arrow("M190,768 V842", "w")
    s.arrow("M510,768 V842", "w")
    s.arrow("M800,768 V842", "w")

    s.band(976, 128, "ВЫХОД ПРОГОНА (runs/<run_id>/)", "#f0ecf6")
    s.box(40, 1016, 440, 76, "forecasts.parquet", [
        "route, ts, yhat, q10, q90 · 61 день почасово", "маршрут 5 без истории → 0 (cold start)",
    ], title_size=14)
    s.box(500, 1016, 460, 76, "effects.parquet", [
        "контрольные прогоны ансамбля без праздников", "и без каникул → log_effect для слайдеров",
    ], title_size=14)
    s.box(980, 1016, 464, 76, "meta.json", [
        "model = ensemble_cal_school_daytype_profile", "ковариаты, квантили, проверки качества",
    ], title_size=14)
    s.arrow("M260,942 V1016", "w")
    s.arrow("M730,942 V1016", "w")
    s.arrow("M900,942 V980 H1210 V1016", "w")
    s.save("ensemble.svg")


docker_diagram()
pipeline_diagram()
ensemble_diagram()
print("ok")
