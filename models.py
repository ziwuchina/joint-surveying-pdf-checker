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
    summary_page: int = -1

    def subitem_sum_measured(self) -> Optional[Decimal]:
        parts = [self.main_function.measured, self.roof_stair.measured,
                 self.facility.measured, self.basement.measured]
        valid = [p for p in parts if p is not None]
        if not valid:
            return None
        return sum(valid, Decimal("0"))

    def subitem_sum_permitted(self) -> Optional[Decimal]:
        parts = [self.main_function.permitted, self.roof_stair.permitted,
                 self.facility.permitted, self.basement.permitted]
        valid = [p for p in parts if p is not None]
        if not valid:
            return None
        return sum(valid, Decimal("0"))

    def subitem_sum_finishing(self) -> Optional[Decimal]:
        parts = [self.main_function.finishing, self.roof_stair.finishing, self.facility.finishing]
        valid = [p for p in parts if p is not None]
        if not valid:
            return None
        return sum(valid, Decimal("0"))

    def far_subitem_sum_measured(self) -> Optional[Decimal]:
        parts = [self.main_function.measured, self.facility.measured]
        valid = [p for p in parts if p is not None]
        if not valid:
            return None
        return sum(valid, Decimal("0"))


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
