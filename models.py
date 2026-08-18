from dataclasses import dataclass, field
from typing import Optional
from decimal import Decimal

TOL = Decimal("0.02")


def d(val) -> Optional[Decimal]:
    if val is None or val == "" or val == "—":
        return None
    try:
        return Decimal(str(val).strip())
    except Exception:
        return None


def normalize_building_name(name: str) -> str:
    """统一建筑名称，作为跨表关联的唯一键。
    处理：空白（半角/全角/换行）、幢→栋、號→号、全角字符转半角。
    """
    if not name:
        return ""
    value = str(name)
    # 全角数字/字母 → 半角
    for fc, hc in [("０", "0"), ("１", "1"), ("２", "2"), ("３", "3"), ("４", "4"),
                   ("５", "5"), ("６", "6"), ("７", "7"), ("８", "8"), ("９", "9")]:
        value = value.replace(fc, hc)
    value = value.replace("\u3000", "").replace(" ", "").replace("\n", "").replace("\t", "")
    value = value.replace("幢", "栋").replace("號", "号").replace("号楼", "栋")
    return value


def fuzzy_building_key(name: str) -> str:
    """模糊匹配 key：在 normalize 基础上再去掉尾部量词（栋/座/幢/号楼/#），
    使「13栋」「13座」「13 号」「13#」等不同命名可互相匹配。
    """
    value = normalize_building_name(name)
    value = value.rstrip("#").rstrip("＃")
    for suffix in ("号楼", "栋", "座", "号", "幢"):
        if value.endswith(suffix) and len(value) > len(suffix):
            return value[:-len(suffix)]
    return value


@dataclass
class AreaItem:
    permitted: Optional[Decimal] = None
    measured: Optional[Decimal] = None
    finishing: Optional[Decimal] = None


@dataclass
class BuildingArea:
    name: str = ""
    base_area: AreaItem = field(default_factory=AreaItem)
    total_area: AreaItem = field(default_factory=AreaItem)
    far_area: AreaItem = field(default_factory=AreaItem)
    main_function: AreaItem = field(default_factory=AreaItem)
    roof_stair: AreaItem = field(default_factory=AreaItem)
    facility: AreaItem = field(default_factory=AreaItem)
    basement: AreaItem = field(default_factory=AreaItem)
    # 使用表格实际出现的分项名称作为键，避免依赖固定的分项字段。
    subitems: dict = field(default_factory=dict)
    # 计容面积汇总表有自己的分项区块，单独存储。
    far_subitems: dict = field(default_factory=dict)
    summary_page: int = -1

    def _all_subitems(self):
        if self.subitems:
            return self.subitems.values()
        return (self.main_function, self.roof_stair, self.facility, self.basement)

    def _all_far_subitems(self):
        if self.far_subitems:
            return self.far_subitems.values()
        if self.subitems:
            return self.subitems.values()
        return (self.main_function, self.roof_stair, self.facility, self.basement)

    def subitem_sum_measured(self) -> Optional[Decimal]:
        vals = [item.measured for item in self._all_subitems()
                if item.measured is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))

    def subitem_sum_permitted(self) -> Optional[Decimal]:
        vals = [item.permitted for item in self._all_subitems()
                if item.permitted is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))

    def subitem_sum_finishing(self) -> Optional[Decimal]:
        vals = [item.finishing for item in self._all_subitems()
                if item.finishing is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))

    def far_subitem_sum_measured(self) -> Optional[Decimal]:
        vals = [item.measured for item in self._all_far_subitems()
                if item.measured is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))

    def far_subitem_sum_permitted(self) -> Optional[Decimal]:
        vals = [item.permitted for item in self._all_far_subitems()
                if item.permitted is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))


@dataclass
class FloorArea:
    floor_name: str = ""
    public_area: Optional[Decimal] = None
    workshop_area: Optional[Decimal] = None
    unshared_public_area: Optional[Decimal] = None


@dataclass
class FloorAreaTable:
    building_name: str = ""
    floors: list = field(default_factory=list)
    total_workshop: Optional[Decimal] = None
    total_inner: Optional[Decimal] = None
    total_shared_public: Optional[Decimal] = None
    total_unshared_public: Optional[Decimal] = None
    total_public: Optional[Decimal] = None
    total_building: Optional[Decimal] = None
    reserved_inner: Optional[Decimal] = None
    summary_page: int = -1
    detail_page: int = -1

    def floor_public_sum(self) -> Optional[Decimal]:
        vals = [f.public_area for f in self.floors if f.public_area is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))

    def floor_workshop_sum(self) -> Optional[Decimal]:
        vals = [f.workshop_area for f in self.floors if f.workshop_area is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))


@dataclass
class UnitArea:
    unit_name: str = ""
    usage: str = ""
    inner_area: Optional[Decimal] = None
    shared_area: Optional[Decimal] = None

    @property
    def building_area(self) -> Optional[Decimal]:
        if self.inner_area is not None and self.shared_area is not None:
            return self.inner_area + self.shared_area
        return None


@dataclass
class UnitAreaTable:
    building_name: str = ""
    units: list = field(default_factory=list)
    total_inner: Optional[Decimal] = None
    total_shared: Optional[Decimal] = None

    @property
    def total_building(self) -> Optional[Decimal]:
        if self.total_inner is not None and self.total_shared is not None:
            return self.total_inner + self.total_shared
        return None

    def unit_inner_sum(self) -> Optional[Decimal]:
        vals = [u.inner_area for u in self.units if u.inner_area is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))

    def unit_shared_sum(self) -> Optional[Decimal]:
        vals = [u.shared_area for u in self.units if u.shared_area is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))


@dataclass
class ApportionmentSource:
    name: str = ""
    area: Optional[Decimal] = None


@dataclass
class ApportionmentInfo:
    building_name: str = ""
    coefficient: Optional[Decimal] = None
    total_inner: Optional[Decimal] = None
    total_shared: Optional[Decimal] = None
    total_building: Optional[Decimal] = None
    sources: list = field(default_factory=list)
    summary_inner: Optional[Decimal] = None
    summary_shared: Optional[Decimal] = None
    summary_building: Optional[Decimal] = None
    page: int = -1

    def source_sum(self) -> Optional[Decimal]:
        vals = [s.area for s in self.sources if s.area is not None]
        if not vals:
            return None
        return sum(vals, Decimal("0"))


@dataclass
class PlanningIndicators:
    base_area_permit: Optional[Decimal] = None
    base_area_measure: Optional[Decimal] = None
    total_area_permit: Optional[Decimal] = None
    total_area_measure: Optional[Decimal] = None
    total_FAR_area_permit: Optional[Decimal] = None
    total_FAR_area_measure: Optional[Decimal] = None
    green_area_permit: Optional[Decimal] = None
    green_area_measure: Optional[Decimal] = None
    certifiable_area: Optional[Decimal] = None
    non_certifiable_area: Optional[Decimal] = None
    real_estate_total_area: Optional[Decimal] = None
    finishing_base_area: Optional[Decimal] = None
    finishing_building_area: Optional[Decimal] = None
    indicator_page: int = -1
    overview_page: int = -1


@dataclass
class EDBUnitArea:
    building_name: str = ""
    floor_areas: dict = field(default_factory=dict)

    def get_floor_workshops(self, floor_num):
        return self.floor_areas.get(floor_num, [])

    def total_workshop_count(self):
        return sum(len(v) for v in self.floor_areas.values())


@dataclass
class CheckResult:
    category: str = ""
    check_name: str = ""
    status: str = "pass"
    expected: str = ""
    actual: str = ""
    detail: str = ""
    page_hint: str = ""
    page_num: int = -1
    calc_process: str = ""


@dataclass
class ReportData:
    buildings: list = field(default_factory=list)
    floor_tables: list = field(default_factory=list)
    unit_tables: list = field(default_factory=list)
    apportionments: list = field(default_factory=list)
    planning: Optional[PlanningIndicators] = None
    edb_unit_areas: list = field(default_factory=list)
    pdf_path: str = ""
    total_pages: int = 0
