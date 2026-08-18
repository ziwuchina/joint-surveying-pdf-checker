import win32com.client
from decimal import Decimal
from models import (
    d, BuildingArea, AreaItem, FloorArea, FloorAreaTable,
    PlanningIndicators, ReportData, EDBUnitArea,
)


class EDBReader:
    def __init__(self, edb_path):
        self.edb_path = edb_path
        self.conn = None

    def connect(self):
        self.conn = win32com.client.Dispatch('ADODB.Connection')
        self.conn.Open(
            f'Provider=Microsoft.ACE.OLEDB.12.0;Data Source={self.edb_path};'
        )

    def close(self):
        if self.conn and self.conn.State == 1:
            self.conn.Close()

    def _query(self, sql):
        rs = win32com.client.Dispatch('ADODB.Recordset')
        rs.Open(sql, self.conn, 1, 1)
        rows = []
        while not rs.EOF:
            row = {}
            for i in range(rs.Fields.Count):
                row[rs.Fields(i).Name] = rs.Fields(i).Value
            rows.append(row)
            rs.MoveNext()
        rs.Close()
        return rows

    def read_buildings(self):
        rows = self._query(
            "SELECT * FROM [GH_建设工程建筑单体信息属性表] WHERE 栋号 <> '*'"
        )
        buildings = []
        for r in rows:
            b = BuildingArea(name=r['栋号'])
            b.base_area = AreaItem(
                permitted=d(r['建设许可基底面积']),
                measured=d(r['验收测量基底面积']),
                finishing=d(r['饰面基底面积']),
            )
            b.total_area = AreaItem(
                permitted=d(r['建设许可总建筑面积']),
                measured=d(r['验收测量总建筑面积']),
                finishing=d(r['饰面总建筑面积']),
            )
            b.far_area = AreaItem(
                permitted=d(r['建设许可总计容面积']),
                measured=d(r['验收测量总计容面积']),
                finishing=d(r['饰面总计容面积']),
            )
            buildings.append(b)
        return buildings

    def read_subitems(self):
        rows = self._query(
            "SELECT * FROM [GH_建筑物单体建筑面积指标核实信息属性表] "
            "WHERE 栋号 <> '*' ORDER BY 栋号,功能类型"
        )
        result = {}
        for r in rows:
            name = r['栋号']
            ftype = r['功能类型']
            fname = r['功能名称'] or ""
            item = AreaItem(
                permitted=d(r['建设许可建筑面积']),
                measured=d(r['验收测量建筑面积']),
                finishing=d(r['饰面建筑面积']),
            )
            if name not in result:
                result[name] = []
            result[name].append((ftype, fname, item))
        return result

    def _classify_subitem(self, ftype, fname, item, building):
        # 与 PDF 解析共用 rules.json 的分项分类规则，保证 EDB/PDF 两侧类别名一致
        from rules import get_subitem_category
        if ftype == '主要功能':
            building.main_function = item
        else:
            cat = get_subitem_category(fname)
            if cat == 'roof':
                building.roof_stair = item
            elif cat == 'facility':
                building.facility = item
            elif cat == 'basement':
                building.basement = item

    def read_planning_indicators(self):
        rows = self._query(
            "SELECT * FROM [GH_建设工程规划许可证信息属性表] "
            "WHERE 建设项目名称 <> '*'"
        )
        if not rows:
            return None
        r = rows[0]
        pi = PlanningIndicators()
        pi.base_area_permit = d(r['建设许可基底面积'])
        pi.base_area_measure = d(r['验收测量基底面积'])
        pi.total_area_permit = d(r['建设许可总建筑面积'])
        pi.total_area_measure = d(r['验收测量总建筑面积'])
        pi.total_FAR_area_permit = d(r['建设许可总计容面积'])
        pi.total_FAR_area_measure = d(r['验收测量总计容面积'])
        pi.green_area_permit = d(r['建设许可绿化面积'])
        pi.green_area_measure = d(r['验收测量绿化面积'])
        return pi

    def read_floor_tables(self, building_names):
        if not building_names:
            return []
        name_list = ",".join(f"'{n}'" for n in building_names)
        sql = (
            f"SELECT LJZH,CH,SJC,CJZMJ,CTNJZMJ,CGYJZMJ,CFTJZMJ,CBQMJ "
            f"FROM [FC_楼层信息属性表] "
            f"WHERE LJZH IN ({name_list}) AND CJZMJ > 0 "
            f"ORDER BY LJZH,SJC,CH"
        )
        rows = self._query(sql)

        tables_by_building = {}
        for r in rows:
            ljzh = r['LJZH']
            ch = str(r['CH'])
            sjc = r['SJC']

            if ljzh not in tables_by_building:
                tables_by_building[ljzh] = {}
            floor_key = f"{sjc:.0f}_{ch}"

            if floor_key not in tables_by_building[ljzh]:
                tables_by_building[ljzh][floor_key] = {
                    'ch': ch,
                    'sjc': sjc,
                    'cjzmj': r['CJZMJ'],
                    'ctnjzmj': r['CTNJZMJ'],
                    'cgyjzmj': r['CGYJZMJ'],
                    'cftjzmj': r['CFTJZMJ'],
                    'cbqmj': r['CBQMJ'],
                }

        result = []
        for bname, floors_dict in tables_by_building.items():
            fat = FloorAreaTable(building_name=bname)
            sorted_keys = sorted(floors_dict.keys(),
                                 key=lambda k: floors_dict[k]['sjc'])
            for key in sorted_keys:
                f = floors_dict[key]
                fa = FloorArea(
                    floor_name=f['ch'],
                    public_area=d(f['cgyjzmj']),
                    workshop_area=d(f['ctnjzmj']),
                )
                fat.floors.append(fa)

            cjzmj_vals = [d(floors_dict[k]['cjzmj']) for k in sorted_keys]
            ctnjzmj_vals = [d(floors_dict[k]['ctnjzmj']) for k in sorted_keys]
            cgyjzmj_vals = [d(floors_dict[k]['cgyjzmj']) for k in sorted_keys]

            if ctnjzmj_vals:
                fat.total_inner = sum(ctnjzmj_vals, Decimal("0"))
            if cgyjzmj_vals:
                fat.total_public = sum(cgyjzmj_vals, Decimal("0"))
            if cjzmj_vals:
                fat.total_building = sum(cjzmj_vals, Decimal("0"))

            result.append(fat)
        return result

    def read_unit_areas(self, building_names):
        if not building_names:
            return []
        name_list = ",".join(f"'{n}'" for n in building_names)
        sql = (
            f"SELECT LJZH,CH,MJKMC,JZMJ FROM [FC_面积块信息属性表] "
            f"WHERE LJZH IN ({name_list}) AND MJKMC='车间' AND JZMJ > 0 "
            f"ORDER BY LJZH,CH"
        )
        rows = self._query(sql)

        result = {}
        for r in rows:
            ljzh = r['LJZH']
            ch = r['CH']
            jzmj = d(r['JZMJ'])
            if jzmj is None or jzmj <= 0:
                continue

            try:
                floor_num = int(float(ch))
            except (ValueError, TypeError):
                continue

            if floor_num != float(ch):
                continue

            rounded = jzmj.quantize(Decimal("0.01"))

            if ljzh not in result:
                result[ljzh] = EDBUnitArea(building_name=ljzh)
            if floor_num not in result[ljzh].floor_areas:
                result[ljzh].floor_areas[floor_num] = []

            already_exists = any(
                abs(existing - rounded) < Decimal("0.02")
                for existing in result[ljzh].floor_areas[floor_num]
            )
            if not already_exists:
                result[ljzh].floor_areas[floor_num].append(rounded)

        return list(result.values())

    def read_all(self):
        self.connect()
        try:
            buildings = self.read_buildings()
            subitems = self.read_subitems()
            planning = self.read_planning_indicators()

            for b in buildings:
                si_list = subitems.get(b.name, [])
                for ftype, fname, item in si_list:
                    self._classify_subitem(ftype, fname, item, b)
                    # 同步填入 subitems 字典（使用 EDB 实际功能名称作为 key），
                    # 使 checker 的 _dynamic_subitems 走 PDF/EDB 同名字典分支，
                    # 避免 EDB 的"主要功能" vs PDF 的"厂房"名称错位导致误报 PDF缺失。
                    if fname:
                        b.subitems[fname] = item

            building_names = [b.name for b in buildings]
            floor_tables = self.read_floor_tables(building_names)
            unit_areas = self.read_unit_areas(building_names)

            report = ReportData(
                buildings=buildings,
                floor_tables=floor_tables,
                planning=planning,
                edb_unit_areas=unit_areas,
                pdf_path=self.edb_path,
            )
            return report
        finally:
            self.close()
