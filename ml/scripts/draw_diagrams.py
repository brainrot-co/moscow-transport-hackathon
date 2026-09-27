from pathlib import Path
from xml.sax.saxutils import escape

DOCS = Path(__file__).resolve().parents[2] / "docs"
INK, MUTED, BORDER, BG = "#1f2426", "#5f686c", "#737b7f", "#f5f5f5"
WRITE, READ = "#b3302a", "#2c6a6e"
FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', SFMono-Regular, Menlo, Consolas, monospace"


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

    def box(self, x: int, y: int, w: int, h: int, title: str, lines: list[str] = (), dashed: bool = False, stroke: str = BORDER, fill: str = "#ffffff", title_size: int = 15, lead: bool = False):
        dash = ' stroke-dasharray="7 5"' if dashed else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>')
        self.parts.append(f'<text x="{x + 14}" y="{y + 26}" font-size="{title_size}" font-weight="600" fill="{INK}">{escape(title)}</text>')
        for i, line in enumerate(lines):
            # lead: первая строка — что делает блок, темнее остальных
            style = f'fill="{INK}" font-weight="500"' if lead and i == 0 else f'fill="{MUTED}"'
            self.parts.append(f'<text x="{x + 14}" y="{y + 48 + 18 * i}" font-size="12.5" {style}>{escape(line)}</text>')

    def card(self, x: int, y: int, w: int, title: str, items: list[tuple], dashed: bool = False, stroke: str = BORDER, fill: str = "#ffffff", title_size: int = 15):
        """Блок с высотой по содержимому; возвращает нижнюю границу.
        items: ("lead", текст) — что и зачем; ("group", подпись) — заголовок группы;
        ("line", текст); ("code", команда); ("row", путь, пояснение, отступ колонки); ("gap",)."""
        body, cy = [], y + 26
        for item in items:
            kind = item[0]
            if kind == "gap":
                cy += 8
                continue
            cy += 22 if kind == "group" else 19
            if kind == "lead":
                body.append(f'<text x="{x + 14}" y="{cy}" font-size="13" font-weight="600" fill="{INK}">{escape(item[1])}</text>')
            elif kind == "group":
                body.append(f'<text x="{x + 14}" y="{cy}" font-size="10.5" font-weight="700" letter-spacing="0.8" fill="{MUTED}">{escape(item[1].upper())}</text>')
            elif kind == "line":
                body.append(f'<text x="{x + 14}" y="{cy}" font-size="12.5" fill="{MUTED}">{escape(item[1])}</text>')
            elif kind == "code":
                body.append(f'<text x="{x + 14}" y="{cy}" font-size="12" font-family="{MONO}" fill="{INK}">{escape(item[1])}</text>')
            elif kind == "row":
                _, path, note, offset = item
                body.append(f'<text x="{x + 14}" y="{cy}" font-size="12" font-family="{MONO}" fill="{INK}">{escape(path)}</text>')
                note_x = x + 14 + offset if offset else x + 14 + 8 * len(path) + 12
                body.append(f'<text x="{note_x}" y="{cy}" font-size="12.5" fill="{MUTED}">{escape(note)}</text>')
        h = cy - y + 16
        self.box(x, y, w, h, title, [], dashed=dashed, stroke=stroke, fill=fill, title_size=title_size)
        self.parts.extend(body)
        return y + h

    def text(self, x: float, y: float, value: str, color: str = MUTED, size: float = 12, anchor: str = "start", weight: int = 400):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>')

    def arrow(self, path: str, kind: str = "m", both: bool = False, dashed: bool = False):
        color = {"w": WRITE, "r": READ, "m": MUTED}[kind]
        start = f' marker-start="url(#a-{kind})"' if both else ""
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="url(#a-{kind})"{start}/>')

    def set_height(self, height: int):
        old = f'height="{self.h}"'
        self.parts = [
            part.replace(f'0 0 {self.w} {self.h}', f'0 0 {self.w} {height}').replace(old, f'height="{height}"')
            if part.startswith(("<svg", "<rect width")) else part
            for part in self.parts
        ]
        self.h = height

    def save(self, path: str):
        (DOCS / path).write_text("\n".join([*self.parts, "</svg>"]), encoding="utf-8")


def docker_diagram():
    s = Svg(1440, 1060, "Логика Docker: контейнеры и общий том")
    lx, lw = 40, 340
    vx, vw = 480, 520
    sx, sw = vx + 20, vw - 40
    rx, rw = 1080, 320

    s.card(lx, 84, lw, "Источник выгрузок", [
        ("lead", "Откуда приходят данные"),
        ("line", "CSV валидаций → inbox/ на томе"),
    ], dashed=True, title_size=14)
    s.card(lx, 190, lw, "./dataset", [
        ("lead", "История для начальной загрузки"),
        ("line", "train.csv и test.csv, только чтение"),
        ("line", "нужна только для make load-history"),
    ], dashed=True, title_size=14)
    ingest_bottom = s.card(lx, 314, lw, "ingest", [
        ("lead", "Приём данных: CSV → почасовой факт"),
        ("group", "как работает"),
        ("line", "1. раз в 60 с проверяет inbox/"),
        ("line", "2. разбор → сырой слой → факт маршрут × час"),
        ("line", "3. статусы дней → водяной знак"),
        ("line", "4. пустой том → стартовый прогноз ml/seed/"),
        ("gap",),
        ("line", "образ ~0.7 ГБ"),
        ("line", "лимит 1 CPU и 2 ГБ памяти"),
        ("code", "python -m mtml.ingest run"),
    ], stroke=WRITE)
    worker_top = ingest_bottom + 90
    worker_bottom = s.card(lx, worker_top, lw, "ml-worker", [
        ("lead", "Прогноз: факт → прогноз на 61 день и год"),
        ("group", "как работает"),
        ("line", "1. ждёт сдвига водяного знака или ночи 03:00"),
        ("line", "2. краткосрочный ансамбль Chronos-2 + эффекты"),
        ("line", "3. годовая сезонная модель"),
        ("line", "4. проверка качества → публикация → мониторинг"),
        ("gap",),
        ("line", "образ ~2.9 ГБ с весами модели внутри"),
        ("line", "лимит 2 CPU и 3 ГБ памяти"),
        ("code", "python -m mtml.worker run"),
    ], stroke=WRITE)
    hf_top = worker_bottom + 50
    hf_bottom = s.card(lx, hf_top, lw, "Hugging Face", [
        ("lead", "Веса Chronos-2"),
        ("line", "скачиваются только при сборке образа"),
    ], dashed=True, title_size=14)

    volume_at = len(s.parts)
    s.text(vx + 14, 120, "единственная связь между сервисами: ML пишет, бэкенд читает", color=READ, size=12.5)
    col = 250
    ing_vol_bottom = s.card(sx, 138, sw, "пишет ingest", [
        ("lead", "Входящие данные и факт"),
        ("group", "приём"),
        ("row", "inbox/ → processed/ или failed/", "новые CSV", col),
        ("row", "ingestion/", "журнал загрузок, карантин", col),
        ("group", "данные"),
        ("row", "raw/validations/", "посадки по дням, без дублей", col),
        ("row", "actuals/actuals_hourly.parquet", "факт маршрут × час", col),
        ("row", "actuals/day_status.parquet", "final, partial или missing", col),
        ("row", "state/watermark.json", "последний полный день", col),
        ("group", "служебное"),
        ("row", "tmp/duckdb/", "сброс памяти на больших файлах", col),
    ], fill="#fbeeed", stroke=WRITE, title_size=14)
    wrk_vol_top = ing_vol_bottom + 24
    wrk_vol_bottom = s.card(sx, wrk_vol_top, sw, "пишет ml-worker", [
        ("lead", "Прогнозы и справочники"),
        ("group", "прогон: новая папка на каждый пересчёт"),
        ("row", "runs/<id>/forecasts.parquet", "прогноз и интервал", col),
        ("row", "runs/<id>/effects.parquet", "эффекты для слайдеров", col),
        ("row", "runs/<id>/meta.json", "модель, данные, проверки", col),
        ("group", "указатели и состояние"),
        ("row", "active.json", "какие прогоны сейчас актуальны", col),
        ("row", "state/worker.json", "последний прогон, ошибка", col),
        ("group", "для бэкенда"),
        ("row", "monitoring/accuracy.parquet", "точность прошлых прогонов", col),
        ("row", "reference/", "календарь, справочник поправок", col),
    ], fill="#fbeeed", stroke=WRITE, title_size=14)
    clock_top = wrk_vol_bottom + 24
    clock_bottom = s.card(sx, clock_top, sw, "общее для всех сервисов", [
        ("row", "state/clock.json", "«сейчас» системы", col),
        ("line", "в проде реальное время, а в демо с 28.10.2025 и в 750 раз быстрее"),
    ], title_size=14)
    s.text(vx + vw / 2, clock_bottom + 36, "бэкенд подключает том только на чтение (:ro)", color=READ, size=12.5, anchor="middle", weight=600)
    volume_bottom = clock_bottom + 60
    s.box(vx, 76, vw, volume_bottom - 76, "Том tram-data (/data)", [], dashed=True, stroke=READ, fill="#eef4f4", title_size=17)
    s.parts[volume_at:volume_at] = s.parts[-2:]
    del s.parts[-2:]

    s.card(rx, 84, rw, "PostgreSQL + Redis", [
        ("lead", "Данные пользователей"),
        ("line", "учётные записи, сценарии, поправки"),
    ], dashed=True, title_size=14)
    backend_top = 250
    backend_bottom = s.card(rx, backend_top, rw, "backend", [
        ("lead", "API: отдаёт прогноз фронтенду"),
        ("group", "как работает"),
        ("line", "1. раз в 30 с проверяет active.json"),
        ("line", "2. новый прогон → в память, без простоя"),
        ("line", "3. склейка: факт → краткосрочный → годовой"),
        ("line", "4. поправки, агрегация, уровень загрузки"),
        ("gap",),
        ("line", "FastAPI, том подключён только на чтение"),
    ], stroke=READ)
    front_top = backend_bottom + 80
    front_bottom = s.card(rx, front_top, rw, "frontend", [
        ("lead", "Дашборд диспетчера"),
        ("line", "карта MapLibre: линии и остановки"),
        ("line", "графики: сутки, неделя, месяц, год"),
        ("line", "поправки с превью, экспорт CSV"),
        ("gap",),
        ("line", "React и nginx, к backend ходит только по HTTP"),
    ])
    disp_top = front_bottom + 60
    disp_bottom = s.card(rx, disp_top, rw, "Диспетчер", [("line", "браузер")], dashed=True, title_size=14)

    # источник → inbox
    s.arrow(f"M{lx + lw},118 C {lx + lw + 60},118 {sx - 50},170 {sx},170")
    s.text(lx + lw + 10, 108, "CSV → inbox/")
    s.arrow(f"M{lx + lw / 2},{190 + 88} V314")
    # ingest ↔ том
    s.arrow(f"M{lx + lw},350 H{sx}", "w", both=True)
    s.text(lx + lw + 10, 342, "чтение и запись", color=WRITE)
    # worker читает факты
    s.arrow(f"M{sx},{ing_vol_bottom - 14} C {sx - 60},{ing_vol_bottom - 14} {lx + lw + 40},{worker_top + 40} {lx + lw},{worker_top + 40}", "r")
    s.text(lx + 14, ingest_bottom + 50, "читает факты, статусы и водяной знак", color=READ)
    # worker пишет прогнозы
    s.arrow(f"M{lx + lw},{worker_top + 150} C {lx + lw + 60},{worker_top + 150} {sx - 60},{wrk_vol_top + 60} {sx},{wrk_vol_top + 60}", "w")
    s.text(lx + lw + 10, worker_top + 180, "пишет прогнозы", color=WRITE)
    s.arrow(f"M{lx + lw / 2},{hf_top} V{worker_bottom}")
    # том → backend
    s.arrow(f"M{vx + vw},{backend_top + 60} H{rx}", "r")
    s.text(vx + vw + 8, backend_top + 50, "только", color=READ)
    s.text(vx + vw + 8, backend_top + 80, "чтение", color=READ)
    s.arrow(f"M{rx + rw / 2},{84 + 88} V{backend_top}", both=True)
    s.arrow(f"M{rx + rw / 2},{backend_bottom} V{front_top}", both=True)
    s.text(rx + rw / 2 + 10, (backend_bottom + front_top) / 2 + 4, "HTTP API")
    s.arrow(f"M{rx + rw / 2},{front_bottom} V{disp_top}", both=True)
    s.set_height(max(hf_bottom, volume_bottom, disp_bottom) + 30)
    s.save("architecture-domain/docker-architecture.svg")


def pipeline_diagram():
    s = Svg(1480, 1110, "Пайплайн: от прихода данных до бэкенда и фронтенда")
    xs = [200, 450, 700, 950, 1200]
    bw = 230

    s.band(64, 118, "ПРИХОД", "#ececec")
    s.box(xs[0], 82, bw, 84, "Источник выгрузок", ["откуда приходят данные", "CSV валидаций от инженеров"], dashed=True, lead=True)
    s.box(xs[1], 82, bw, 84, "inbox/*.csv", ["папка приёма на томе", "пишется как .part, затем .csv"], lead=True)
    s.box(xs[4], 82, bw, 84, "state/clock.json", ["«сейчас» для всех сервисов", "в демо с 28.10.2025 03:00"], dashed=True, lead=True)
    s.arrow(f"M{xs[0] + bw},124 H{xs[1]}")

    s.band(204, 140, "INGEST", "#fbeeed")
    ingest = [
        ("Разбор", ["проверить и привести типы", "отказы только считаются,", "битые строки в карантин"]),
        ("Сырой слой", ["посадки по дням без дублей", "ключ: устройство, транзакция", "и время валидации"]),
        ("Факты", ["посадки маршрут × час", "затронутые дни", "пересчитываются целиком"]),
        ("Статусы дней", ["полные ли данные за день", "final, partial или missing", "и флаг anomaly (ремонт)"]),
        ("Водяной знак", ["последний полный день", "state/watermark.json"]),
    ]
    for x, (title, lines) in zip(xs, ingest, strict=True):
        s.box(x, 230, bw, 98, title, lines, stroke=WRITE, lead=True)
    for a, b in zip(xs, xs[1:]):
        s.arrow(f"M{a + bw},279 H{b}", "w")
    s.arrow(f"M{xs[1] + bw / 2},166 V230", "w")
    s.arrow(f"M{xs[4] + bw / 2},166 V230", dashed=True)
    s.text(xs[4] + bw / 2 + 8, 200, "возраст дня")

    s.band(366, 340, "ML-WORKER", "#e8f1f1")
    worker = [
        ("Расписание", ["когда пересчитывать", "сдвиг водяного знака или 03:00", "не чаще MIN_RERUN_MINUTES"]),
        ("Контекст", ["история для модели", "факт до водяного знака", "маршрут без посадок: cold start"]),
        ("Краткосрочный", ["прогноз на 61 день по часам", "ансамбль RH, RHD и V2", "календарь, каникулы, тип дня"]),
        ("Эффекты", ["сила праздников и каникул", "прогоны без фактора", "и запись в effects.parquet"]),
        ("Проверки и публикация", ["публикуется только хороший", "сетка, пропуски, суммы недель", "runs/<id>/, затем active.json"]),
    ]
    for x, (title, lines) in zip(xs, worker, strict=True):
        s.box(x, 392, bw, 98, title, lines, stroke=READ, lead=True)
    for a, b in zip(xs, xs[1:]):
        s.arrow(f"M{a + bw},441 H{b}", "r")
    s.box(xs[2], 520, bw, 84, "Годовой", ["прогноз до 365 дней", "месяц, тип дня и каникулы"], stroke=READ, lead=True)
    s.box(xs[0], 520, bw, 120, "Входы моделей", ["справочники и веса", "календарь 2025–26 и каникулы", "веса Chronos-2 в образе,", "сеть при работе не нужна"], dashed=True, title_size=14, lead=True)
    s.box(xs[4], 606, bw, 84, "Мониторинг", ["точность прошлых прогонов", "monitoring/accuracy.parquet"], stroke=READ, lead=True)
    s.arrow(f"M{xs[1] + bw / 2},490 V562 H{xs[2]}", "r")
    s.arrow(f"M{xs[2] + bw},562 H{xs[4] + bw / 2 - 30} V490", "r")
    s.arrow(f"M{xs[0] + bw},538 C {xs[1] + 120},538 {xs[2] - 20},518 {xs[2] + 40},490", dashed=True)
    s.arrow(f"M{xs[0] + bw},598 H{xs[2]}", dashed=True)
    s.arrow(f"M{xs[4] + bw / 2 + 40},490 V606", "r")
    s.text(xs[4] + bw / 2 + 48, 556, "факты пришли", color=READ)
    s.arrow(f"M{xs[4] + bw / 2},328 V348 H{xs[0] + bw / 2} V392", "r")
    s.text(xs[1] + 20, 344, "водяной знак сдвинулся", color=READ)
    s.arrow(f"M{xs[2] + bw / 2},328 V358 H{xs[1] + bw / 2} V392", "r")
    s.text(xs[1] + bw / 2 + 8, 374, "факты и статусы", color=READ)

    s.band(724, 186, "BACKEND", "#f0ecf6")
    backend = [
        ("Чтение тома", ["прогноз в памяти", "active.json раз в 30 с"]),
        ("Склейка", ["один ряд из трёх источников", "факт, затем short до 61 дня,", "затем year"]),
        ("Поправки", ["правки диспетчера", "слайдеры: сила эффекта k", "сценарии: множитель m"]),
        ("API", ["ответ фронтенду", "маршруты, интервал и шаг,", "уровень загрузки"]),
        ("PostgreSQL", ["данные пользователей", "сценарии и поправки"]),
    ]
    for x, (title, lines) in zip(xs, backend, strict=True):
        s.box(x, 754, bw, 98, title, lines, dashed=title == "PostgreSQL", lead=True)
    for a, b in zip(xs[:3], xs[1:4]):
        s.arrow(f"M{a + bw},803 H{b}")
    s.arrow(f"M{xs[4]},803 H{xs[3] + bw}", both=True)
    s.arrow(f"M{xs[4] + bw},441 H{xs[4] + bw + 22} V736 H{xs[0] + bw / 2} V754", "r")
    s.text(xs[1] + 20, 730, "active.json → новый прогноз (том только на чтение)", color=READ)

    s.band(928, 164, "FRONTEND", "#fbf4e4")
    front = [
        ("Сутки", ["по часам"]),
        ("Неделя", ["по дням и часам"]),
        ("Месяц и год", ["по дням, неделям, месяцам"]),
        ("Поправки и события", ["слайдеры и форма события"]),
        ("Карта и экспорт", ["линии, остановки и CSV"]),
    ]
    for x, (title, lines) in zip(xs, front, strict=True):
        s.box(x, 964, bw, 70, title, lines, lead=True)
    s.arrow(f"M{xs[3] + bw / 2},852 V964", both=True)
    s.text(xs[3] + bw / 2 + 8, 912, "HTTP API")
    s.save("architecture-domain/pipeline.svg")


def ensemble_diagram():
    s = Svg(1480, 1120, "Боевая модель: ensemble_cal_school_daytype_profile")
    xs, bw = [40, 278, 516, 754, 992, 1230], 216

    s.band(64, 146, "ВХОДЫ", "#ececec")
    inputs = [
        ("Факты (actuals)", ["история до водяного знака", "плотная сетка маршрут × час", "из ingest"], False),
        ("calendar.csv · isDayOff", ["is_non_working", "is_holiday_weekday", "is_shortened · 2025–2026"], False),
        ("Школьные каникулы", ["school_holiday_modular", "school_holiday_quarter", "источники в CSV"], False),
        ("Тип дня (covariates.py)", ["workday / saturday / sunday", "holiday / pre_holiday /", "post_holiday"], False),
        ("Chronos-2", ["amazon/chronos-2, zero-shot", "без дообучения", "веса в образе воркера"], False),
        ("Погода (не входит)", ["только эксперименты", "_wx / _pwx", "бэктест: −0.003…−0.006"], True),
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
        "9 рядов — по маршруту", "горизонт 61 день", "ковариат нет", "медиана",
    ], stroke=READ, title_size=13)
    s.box(vx[2], 392, vw, 156, "Chronos-2: суммы + календарь", [
        "9 рядов — по маршруту", "на горизонте:", "is_non_working,", "is_holiday_weekday, dow", "медиана",
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
    s.save("ml-artifacts/ensemble.svg")


docker_diagram()
pipeline_diagram()
ensemble_diagram()
print("ok")
