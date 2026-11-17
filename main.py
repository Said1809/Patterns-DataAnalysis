from __future__ import annotations

import copy
import json
import tkinter as tk
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Iterable, Optional

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CSV = DATA_DIR / "sales.csv"


class AppConfig:
    """Глобальные настройки приложения."""

    _instance: Optional["AppConfig"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.window_title = "Интерактивный анализ набора данных"
            cls._instance.window_size = "1100x700"
            cls._instance.default_metric = "revenue"
            cls._instance.default_group = "region"
        return cls._instance


@dataclass
class AnalysisQuery:
    """Запрос анализа: фильтры, группировка и метрика."""

    metric: str = "revenue"
    group_by: str = "region"
    region: Optional[str] = None
    category: Optional[str] = None
    channel: Optional[str] = None
    chart_kind: str = "bar"

    def clone(self) -> "AnalysisQuery":
        """Создаёт независимую копию запроса."""
        return copy.deepcopy(self)

    def describe(self) -> str:
        parts = [f"метрика={self.metric}", f"группа={self.group_by}", f"график={self.chart_kind}"]
        if self.region:
            parts.append(f"регион={self.region}")
        if self.category:
            parts.append(f"категория={self.category}")
        if self.channel:
            parts.append(f"канал={self.channel}")
        return ", ".join(parts)


class AnalysisQueryBuilder:
    """Пошагово собирает AnalysisQuery."""

    def __init__(self):
        self._query = AnalysisQuery()

    def metric(self, name: str) -> "AnalysisQueryBuilder":
        self._query.metric = name
        return self

    def group_by(self, name: str) -> "AnalysisQueryBuilder":
        self._query.group_by = name
        return self

    def region(self, value: Optional[str]) -> "AnalysisQueryBuilder":
        self._query.region = value or None
        return self

    def category(self, value: Optional[str]) -> "AnalysisQueryBuilder":
        self._query.category = value or None
        return self

    def channel(self, value: Optional[str]) -> "AnalysisQueryBuilder":
        self._query.channel = value or None
        return self

    def chart(self, kind: str) -> "AnalysisQueryBuilder":
        self._query.chart_kind = kind
        return self

    def build(self) -> AnalysisQuery:
        return self._query.clone()


class Dataset(ABC):
    """Набор данных."""

    @abstractmethod
    def as_dataframe(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def columns(self) -> list[str]:
        raise NotImplementedError


class CsvDatasetAdapter(Dataset):
    """Читает CSV как набор данных."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._df = pd.read_csv(self.path)

    def as_dataframe(self) -> pd.DataFrame:
        return self._df.copy()

    def columns(self) -> list[str]:
        return list(self._df.columns)


class JsonDatasetAdapter(Dataset):
    """Читает JSON (список объектов) как набор данных."""

    def __init__(self, path: Path):
        self.path = Path(path)
        with open(self.path, encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict) and "records" in payload:
            payload = payload["records"]
        self._df = pd.DataFrame(payload)

    def as_dataframe(self) -> pd.DataFrame:
        return self._df.copy()

    def columns(self) -> list[str]:
        return list(self._df.columns)


def load_dataset(path: Path) -> Dataset:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return CsvDatasetAdapter(path)
    if suffix == ".json":
        return JsonDatasetAdapter(path)
    raise ValueError(f"Неподдерживаемый формат: {suffix}")


@dataclass(frozen=True)
class ChartStyle:
    color: str
    edgecolor: str
    alpha: float
    title_size: int


class StyleFlyweightFactory:
    """Хранит общие стили отрисовки и отдаёт один и тот же объект повторно."""

    def __init__(self):
        self._styles: dict[str, ChartStyle] = {}

    def get_style(self, name: str) -> ChartStyle:
        if name not in self._styles:
            presets = {
                "bar": ChartStyle("#3B82F6", "#1E3A8A", 0.9, 12),
                "line": ChartStyle("#10B981", "#065F46", 0.95, 12),
                "pie": ChartStyle("#F59E0B", "#92400E", 0.9, 12),
                "default": ChartStyle("#6366F1", "#312E81", 0.9, 12),
            }
            self._styles[name] = presets.get(name, presets["default"])
        return self._styles[name]


STYLE_FLYWEIGHTS = StyleFlyweightFactory()


class ChartRenderer(ABC):
    """Отрисовка графика на осях Matplotlib."""

    @abstractmethod
    def render(self, ax, labels: list[str], values: list[float], style: ChartStyle, title: str):
        raise NotImplementedError


class BarRenderer(ChartRenderer):
    def render(self, ax, labels, values, style, title):
        ax.bar(labels, values, color=style.color, edgecolor=style.edgecolor, alpha=style.alpha)
        ax.set_title(title, fontsize=style.title_size)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("Значение")


class LineRenderer(ChartRenderer):
    def render(self, ax, labels, values, style, title):
        ax.plot(labels, values, marker="o", color=style.color, linewidth=2)
        ax.set_title(title, fontsize=style.title_size)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("Значение")
        ax.grid(True, alpha=0.3)


class PieRenderer(ChartRenderer):
    def render(self, ax, labels, values, style, title):
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title(title, fontsize=style.title_size)


class Chart(ABC):
    """График: выбирает способ отрисовки и стиль."""

    def __init__(self, renderer: ChartRenderer, style_name: str = "default"):
        self.renderer = renderer
        self.style = STYLE_FLYWEIGHTS.get_style(style_name)

    def draw(self, ax, labels: list[str], values: list[float], title: str):
        self.renderer.render(ax, labels, values, self.style, title)


class BarChart(Chart):
    def __init__(self):
        super().__init__(BarRenderer(), "bar")


class LineChart(Chart):
    def __init__(self):
        super().__init__(LineRenderer(), "line")


class PieChart(Chart):
    def __init__(self):
        super().__init__(PieRenderer(), "pie")


class ChartFactory(ABC):
    """Создаёт графики одного семейства."""

    @abstractmethod
    def create_bar(self) -> Chart:
        raise NotImplementedError

    @abstractmethod
    def create_line(self) -> Chart:
        raise NotImplementedError

    @abstractmethod
    def create_pie(self) -> Chart:
        raise NotImplementedError

    def create(self, kind: str) -> Chart:
        mapping = {
            "bar": self.create_bar,
            "line": self.create_line,
            "pie": self.create_pie,
        }
        if kind not in mapping:
            raise ValueError(f"Неизвестный тип графика: {kind}")
        return mapping[kind]()


class MatplotlibChartFactory(ChartFactory):
    """Графики на Matplotlib."""

    def create_bar(self) -> Chart:
        return BarChart()

    def create_line(self) -> Chart:
        return LineChart()

    def create_pie(self) -> Chart:
        return PieChart()


@dataclass
class AnalysisResult:
    labels: list[str]
    values: list[float]
    title: str
    extras: dict[str, Any] = field(default_factory=dict)


class ChartView(ABC):
    @abstractmethod
    def build(self, df: pd.DataFrame, query: AnalysisQuery) -> AnalysisResult:
        raise NotImplementedError

    @abstractmethod
    def draw(self, ax, result: AnalysisResult):
        raise NotImplementedError


class BasicChartView(ChartView):
    def __init__(self, factory: ChartFactory):
        self.factory = factory

    def build(self, df: pd.DataFrame, query: AnalysisQuery) -> AnalysisResult:
        filtered = apply_query(df, query)
        if filtered.empty:
            return AnalysisResult([], [], "Нет данных по запросу")
        grouped = filtered.groupby(query.group_by, dropna=False)[query.metric].sum().sort_values(ascending=False)
        title = f"{query.metric} по {query.group_by}"
        return AnalysisResult(
            labels=[str(x) for x in grouped.index.tolist()],
            values=[float(x) for x in grouped.values.tolist()],
            title=title,
        )

    def draw(self, ax, result: AnalysisResult):
        ax.clear()
        if not result.labels:
            ax.text(0.5, 0.5, result.title, ha="center", va="center")
            ax.axis("off")
            return
        kind = result.extras.get("chart_kind", "bar")
        chart = self.factory.create(kind)
        chart.draw(ax, result.labels, result.values, result.title)


class ChartDecorator(ChartView):
    """Обёртка над представлением графика."""

    def __init__(self, wrapped: ChartView):
        self._wrapped = wrapped

    def build(self, df: pd.DataFrame, query: AnalysisQuery) -> AnalysisResult:
        return self._wrapped.build(df, query)

    def draw(self, ax, result: AnalysisResult):
        self._wrapped.draw(ax, result)


class StatsOverlayDecorator(ChartDecorator):
    """Добавляет к результату сумму, среднее и максимум."""

    def build(self, df: pd.DataFrame, query: AnalysisQuery) -> AnalysisResult:
        result = self._wrapped.build(df, query)
        if result.values:
            result.extras["sum"] = sum(result.values)
            result.extras["avg"] = sum(result.values) / len(result.values)
            result.extras["max"] = max(result.values)
            result.title = f"{result.title} | Σ={result.extras['sum']:.0f}"
        result.extras["chart_kind"] = query.chart_kind
        return result

    def draw(self, ax, result: AnalysisResult):
        self._wrapped.draw(ax, result)
        if "avg" in result.extras and result.labels and result.extras.get("chart_kind") != "pie":
            ax.axhline(result.extras["avg"], color="#EF4444", linestyle="--", linewidth=1.2, label="среднее")
            ax.legend(loc="best")


class MetricNode(ABC):
    @abstractmethod
    def evaluate(self, df: pd.DataFrame) -> float:
        raise NotImplementedError

    @abstractmethod
    def label(self) -> str:
        raise NotImplementedError


class LeafMetric(MetricNode):
    def __init__(self, name: str, column: str):
        self.name = name
        self.column = column

    def evaluate(self, df: pd.DataFrame) -> float:
        if self.column not in df.columns or df.empty:
            return 0.0
        return float(df[self.column].sum())

    def label(self) -> str:
        return self.name


class MetricGroup(MetricNode):
    """Группа метрик, которая считается как одна метрика."""

    def __init__(self, name: str):
        self.name = name
        self.children: list[MetricNode] = []

    def add(self, node: MetricNode) -> "MetricGroup":
        self.children.append(node)
        return self

    def evaluate(self, df: pd.DataFrame) -> float:
        return sum(child.evaluate(df) for child in self.children)

    def label(self) -> str:
        return self.name

    def walk(self) -> Iterable[MetricNode]:
        yield self
        for child in self.children:
            if isinstance(child, MetricGroup):
                yield from child.walk()
            else:
                yield child


def build_default_metric_tree() -> MetricGroup:
    root = MetricGroup("Сводка")
    sales = MetricGroup("Продажи")
    sales.add(LeafMetric("Выручка", "revenue"))
    sales.add(LeafMetric("Единицы", "units"))
    root.add(sales)
    root.add(LeafMetric("Выручка (повтор)", "revenue"))
    return root


def apply_query(df: pd.DataFrame, query: AnalysisQuery) -> pd.DataFrame:
    result = df.copy()
    if query.region:
        result = result[result["region"] == query.region]
    if query.category:
        result = result[result["category"] == query.category]
    if query.channel:
        result = result[result["channel"] == query.channel]
    return result


class Analyzer:
    def __init__(self, factory: Optional[ChartFactory] = None):
        self.factory = factory or MatplotlibChartFactory()
        self.view: ChartView = StatsOverlayDecorator(BasicChartView(self.factory))
        self.metric_tree = build_default_metric_tree()
        self.dataset: Optional[Dataset] = None
        self.df = pd.DataFrame()
        self.last_query: Optional[AnalysisQuery] = None
        self.last_result: Optional[AnalysisResult] = None

    def load(self, path: Path):
        self.dataset = load_dataset(path)
        self.df = self.dataset.as_dataframe()

    def run(self, query: AnalysisQuery) -> AnalysisResult:
        self.last_query = query
        result = self.view.build(self.df, query)
        result.extras.setdefault("chart_kind", query.chart_kind)
        filtered = apply_query(self.df, query)
        summary = {
            node.label(): node.evaluate(filtered)
            for node in self.metric_tree.walk()
            if isinstance(node, LeafMetric)
        }
        result.extras["metric_tree"] = summary
        self.last_result = result
        return result


class AnalysisWindow:
    def __init__(self, analyzer: Analyzer):
        self.config = AppConfig()
        self.analyzer = analyzer
        self.root = tk.Tk()
        self.root.title(self.config.window_title)
        self.root.geometry(self.config.window_size)

        self.region_var = tk.StringVar(value="Все")
        self.category_var = tk.StringVar(value="Все")
        self.channel_var = tk.StringVar(value="Все")
        self.metric_var = tk.StringVar(value=self.config.default_metric)
        self.group_var = tk.StringVar(value=self.config.default_group)
        self.chart_var = tk.StringVar(value="bar")
        self.status_var = tk.StringVar(value="Загрузите набор данных")

        self._prototype_query: Optional[AnalysisQuery] = None
        self._build_ui()
        if DEFAULT_CSV.exists():
            self._load_path(DEFAULT_CSV)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Открыть CSV/JSON", command=self._open_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Анализ", command=self._analyze).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Сохранить запрос", command=self._save_prototype).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Загрузить запрос", command=self._load_prototype).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Сохранить график", command=self._save_chart).pack(side=tk.LEFT, padx=4)

        filters = ttk.LabelFrame(self.root, text="Параметры запроса", padding=8)
        filters.pack(fill=tk.X, padx=8, pady=4)

        self.region_combo = self._add_combo(filters, "Регион", self.region_var, 0)
        self.category_combo = self._add_combo(filters, "Категория", self.category_var, 1)
        self.channel_combo = self._add_combo(filters, "Канал", self.channel_var, 2)
        self._add_combo(filters, "Метрика", self.metric_var, 3, values=["revenue", "units"])
        self._add_combo(filters, "Группировка", self.group_var, 4, values=["region", "category", "channel", "product"])
        self._add_combo(filters, "График", self.chart_var, 5, values=["bar", "line", "pie"])

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)

        self.table = ttk.Treeview(left, show="headings", height=18)
        self.table.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.table.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.table.configure(yscrollcommand=scroll.set)

        self.summary = tk.Text(right, height=6, wrap=tk.WORD)
        self.summary.pack(fill=tk.X)

        self.figure = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.root, textvariable=self.status_var).pack(fill=tk.X, padx=8, pady=4)

    def _add_combo(self, parent, label, variable, column, values=None):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, padx=6, sticky="w")
        ttk.Label(frame, text=label).pack(anchor="w")
        combo = ttk.Combobox(frame, textvariable=variable, width=14, state="readonly")
        if values:
            combo["values"] = values
        combo.pack()
        return combo

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Выберите набор данных",
            filetypes=[("Data files", "*.csv *.json"), ("CSV", "*.csv"), ("JSON", "*.json")],
        )
        if path:
            self._load_path(Path(path))

    def _load_path(self, path: Path):
        try:
            self.analyzer.load(path)
        except Exception as exc:
            messagebox.showerror("Ошибка загрузки", str(exc))
            return
        self._refresh_filter_values()
        self._fill_table(self.analyzer.df)
        self.status_var.set(f"Загружено: {path.name} ({len(self.analyzer.df)} строк)")
        self._analyze()

    def _refresh_filter_values(self):
        df = self.analyzer.df
        self.region_combo["values"] = ["Все"] + sorted(df["region"].dropna().unique().tolist())
        self.category_combo["values"] = ["Все"] + sorted(df["category"].dropna().unique().tolist())
        self.channel_combo["values"] = ["Все"] + sorted(df["channel"].dropna().unique().tolist())
        self.region_var.set("Все")
        self.category_var.set("Все")
        self.channel_var.set("Все")

    def _fill_table(self, df: pd.DataFrame):
        self.table.delete(*self.table.get_children())
        cols = list(df.columns)
        self.table["columns"] = cols
        for col in cols:
            self.table.heading(col, text=col)
            self.table.column(col, width=90, anchor="center")
        for _, row in df.head(200).iterrows():
            self.table.insert("", tk.END, values=[row[c] for c in cols])

    def _current_query(self) -> AnalysisQuery:
        builder = AnalysisQueryBuilder()
        builder.metric(self.metric_var.get())
        builder.group_by(self.group_var.get())
        builder.chart(self.chart_var.get())
        builder.region(None if self.region_var.get() == "Все" else self.region_var.get())
        builder.category(None if self.category_var.get() == "Все" else self.category_var.get())
        builder.channel(None if self.channel_var.get() == "Все" else self.channel_var.get())
        return builder.build()

    def _analyze(self):
        if self.analyzer.df.empty:
            messagebox.showinfo("Нет данных", "Сначала загрузите CSV или JSON")
            return
        query = self._current_query()
        result = self.analyzer.run(query)
        filtered = apply_query(self.analyzer.df, query)
        self._fill_table(filtered)

        lines = [
            f"Запрос: {query.describe()}",
            f"Строк после фильтра: {len(filtered)}",
        ]
        if "sum" in result.extras:
            lines.append(
                f"Статистика: сумма={result.extras['sum']:.2f}, "
                f"среднее={result.extras['avg']:.2f}, макс={result.extras['max']:.2f}"
            )
        tree = result.extras.get("metric_tree", {})
        if tree:
            lines.append("Сводка: " + ", ".join(f"{k}={v:.0f}" for k, v in tree.items()))
        self.summary.delete("1.0", tk.END)
        self.summary.insert(tk.END, "\n".join(lines))

        self.analyzer.view.draw(self.ax, result)
        self.figure.tight_layout()
        self.canvas.draw()
        self.status_var.set("Анализ выполнен")

    def _save_prototype(self):
        self._prototype_query = self._current_query().clone()
        self.status_var.set(f"Запрос сохранён: {self._prototype_query.describe()}")

    def _load_prototype(self):
        if self._prototype_query is None:
            messagebox.showinfo("Запрос", "Сначала сохраните запрос")
            return
        q = self._prototype_query.clone()
        self.metric_var.set(q.metric)
        self.group_var.set(q.group_by)
        self.chart_var.set(q.chart_kind)
        self.region_var.set(q.region or "Все")
        self.category_var.set(q.category or "Все")
        self.channel_var.set(q.channel or "Все")
        self._analyze()
        self.status_var.set("Запрос загружен и применён")

    def _save_chart(self):
        if self.analyzer.last_result is None:
            messagebox.showinfo("График", "Сначала выполните анализ")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            initialfile="analysis-result.png",
        )
        if path:
            self.figure.savefig(path, dpi=140, bbox_inches="tight")
            self.status_var.set(f"График сохранён: {path}")

    def run(self):
        self.root.mainloop()


class AnalysisApp:
    """Запуск приложения анализа данных."""

    def __init__(self, data_path: Optional[Path] = None):
        self.analyzer = Analyzer(MatplotlibChartFactory())
        self.window = AnalysisWindow(self.analyzer)
        if data_path and Path(data_path).exists():
            self.window._load_path(Path(data_path))

    def run(self):
        self.window.run()


def export_demo_chart(output: Path, query: Optional[AnalysisQuery] = None) -> Path:
    """Сохраняет график в файл без окна."""
    analyzer = Analyzer()
    analyzer.load(DEFAULT_CSV)
    query = query or (
        AnalysisQueryBuilder()
        .metric("revenue")
        .group_by("region")
        .chart("bar")
        .build()
    )
    result = analyzer.run(query)
    fig = Figure(figsize=(7, 4), dpi=120)
    ax = fig.add_subplot(111)
    analyzer.view.draw(ax, result)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches="tight")
    return output


if __name__ == "__main__":
    AnalysisApp().run()
