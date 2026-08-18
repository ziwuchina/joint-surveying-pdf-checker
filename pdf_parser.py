import re
import pymupdf
from models import (
    d, BuildingArea, AreaItem, FloorArea, FloorAreaTable,
    UnitArea, UnitAreaTable, ApportionmentInfo, ApportionmentSource,
    PlanningIndicators, ReportData,
)


def _find_pages(doc, keyword, start=0):
    result = []
    for i in range(start, len(doc)):
        if doc[i].search_for(keyword):
            result.append(i)
    return result


def _is_table_page(doc, pidx, exclude_keywords=None):
    text = doc[pidx].get_text()
    if "目录" in text or "作业声明" in text:
        return False
    if exclude_keywords:
        for kw in exclude_keywords:
            if kw in text:
                return False
    return True


def _get_tables(doc, pidx):
    try:
        tabs = doc[pidx].find_tables()
        return list(tabs.tables) if tabs else []
    except Exception:
        return []


def _row_str(row, idx):
    if idx < len(row):
        val = row[idx]
        return str(val).strip() if val else ""
    return ""


def _detect_building_names(header_row):
    """从表头行动态识别建筑名称（列索引→名称）"""
    bldg_cols = {}
    for ci, cell in enumerate(header_row):
        if not cell:
            continue
        name = str(cell).strip().replace('\n', '')
        if not name:
            continue
        if name in ("功能 栋号", "功能\n栋号", "功能栋号", "备注", ""):
            continue
        if name in ("许可", "测量", "饰面"):
            continue
        if re.match(r'^[\d\s]+$', name):
            continue
        bldg_cols[ci] = name
    return bldg_cols


def _detect_sub_type(row_joined):
    """检测当前行的子类型：许可/测量/饰面"""
    for cell in row_joined.split():
        if cell == "许可":
            return "permitted"
        if cell == "测量":
            return "measured"
        if cell == "饰面":
            return "finishing"
    cells = row_joined.replace('\n', '').split()
    for cell in cells:
        if cell == "许可":
            return "permitted"
        if cell == "测量":
            return "measured"
        if cell == "饰面":
            return "finishing"
    return None


def _categorize_subitem(label):
    """将分项面积子项分类"""
    label_clean = label.replace('\n', '').replace(' ', '')
    if any(k in label_clean for k in ["屋面", "屋顶", "梯屋", "机房"]):
        return "roof"
    if any(k in label_clean for k in ["配套", "消防", "水泵", "配电", "发电机", "开关站", "水池"]):
        return "facility"
    if "地下" in label_clean:
        return "basement"
    if any(k in label_clean for k in ["主要功能", "教育", "宿舍", "办公", "车间", "停车", "商业", "住宅"]):
        return "main"
    return "other"


def _parse_area_summary_tables(doc, keyword, page_offset=3):
    buildings = []
    page_idxs = _find_pages(doc, keyword, start=page_offset)

    for pidx in page_idxs:
        if not _is_table_page(doc, pidx, exclude_keywords=["目录"]):
            continue
        if keyword not in doc[pidx].get_text():
            continue

        tables = _get_tables(doc, pidx)
        for tab in tables:
            data = tab.extract()
            if not data or len(data) < 2:
                continue

            header = data[0]
            bldg_cols = _detect_building_names(header)
            if not bldg_cols:
                continue

            for ci, name in bldg_cols.items():
                if not any(b.name == name for b in buildings):
                    b = BuildingArea(name=name)
                    b.summary_page = pidx
                    buildings.append(b)

            is_far = "计容" in keyword
            current_cat = None
            current_sub_cat = None
            current_sub_label = None
            sub_cat_labels = {"主要功能", "其它项目", "其他项目"}

            for row in data[1:]:
                row_texts = [_row_str(row, ci) for ci in range(len(row))]
                row_joined = " ".join(row_texts)
                row_clean = row_joined.replace('\n', '').replace(' ', '')

                if "基底面积" in row_joined:
                    current_cat = "base"
                    current_sub_cat = None
                    current_sub_label = None
                elif "计容面积" in row_joined and "分项" not in row_joined:
                    current_cat = "far"
                    current_sub_cat = None
                    current_sub_label = None
                elif "建筑面积" in row_joined and "分项" not in row_joined and "总" not in row_joined:
                    current_cat = "total"
                    current_sub_cat = None
                    current_sub_label = None
                elif "分项" in row_joined and "面积" in row_joined:
                    current_cat = "subitem"
                    current_sub_cat = None
                    current_sub_label = None
                elif "主要功能" in row_joined:
                    current_sub_cat = "main"
                elif "其它项目" in row_joined or "其他项目" in row_joined:
                    current_sub_cat = "other"

                sub = _detect_sub_type(row_joined)
                if not current_cat or not sub:
                    continue

                sub_label = ""
                for ci in range(len(row)):
                    cell = _row_str(row, ci)
                    if not cell:
                        continue
                    if cell in ("许可", "测量", "饰面"):
                        continue
                    if ci in bldg_cols:
                        continue
                    cell_clean = cell.replace('\n', '').replace(' ', '')
                    if cell_clean in sub_cat_labels or cell_clean == "分项面积":
                        continue
                    if re.match(r'^[\d.]+$', cell):
                        continue
                    sub_label = cell_clean
                    break

                if sub_label:
                    current_sub_label = sub_label
                else:
                    sub_label = current_sub_label or ""

                for ci, bldg_name in bldg_cols.items():
                    val_str = _row_str(row, ci)
                    if not val_str:
                        continue
                    num_val = d(val_str)
                    if num_val is None:
                        continue

                    bld = next((b for b in buildings if b.name == bldg_name), None)
                    if not bld:
                        continue

                    if current_cat == "base":
                        setattr(bld.base_area, sub, num_val)
                    elif current_cat == "total" and not is_far:
                        setattr(bld.total_area, sub, num_val)
                    elif current_cat == "far":
                        setattr(bld.far_area, sub, num_val)
                    elif current_cat == "subitem":
                        # 分项名称因项目而异：以表格实际识别到的名称作为唯一键
                        item_label = (sub_label or current_sub_label or
                                      current_sub_cat or "未命名分项")
                        item_key = re.sub(r"\s+", "", item_label.replace("\n", ""))
                        if not item_key or item_key in {"分项面积", "小计", "合计", "总计"}:
                            continue
                        item = bld.subitems.setdefault(item_key, AreaItem())
                        old_value = getattr(item, sub)
                        setattr(item, sub, num_val if old_value is None else old_value + num_val)

                        # 保留旧字段供兼容
                        cat = _categorize_subitem(sub_label) if sub_label else current_sub_cat or "other"
                        if cat == "main" or current_sub_cat == "main":
                            setattr(bld.main_function, sub, num_val)
                        elif cat == "roof" or current_sub_cat == "roof":
                            setattr(bld.roof_stair, sub, num_val)
                        elif cat == "facility":
                            setattr(bld.facility, sub, num_val)
                        elif cat == "basement":
                            setattr(bld.basement, sub, num_val)

    # "分项面积"是表格节标题被误当作分项名称，实际代表主要功能面积
    for bld in buildings:
        if "分项面积" in bld.subitems and "主要功能" not in bld.subitems:
            item = bld.subitems.pop("分项面积")
            bld.subitems["主要功能"] = item
            bld.main_function = item

    return buildings


def parse_building_area_summary(doc):
    buildings = _parse_area_summary_tables(doc, "建筑面积汇总表")

    far_page_idxs = _find_pages(doc, "计容面积汇总表", start=3)
    for pidx in far_page_idxs:
        if not _is_table_page(doc, pidx, exclude_keywords=["目录"]):
            continue
        tables = _get_tables(doc, pidx)
        for tab in tables:
            data = tab.extract()
            if not data or len(data) < 2:
                continue

            header = data[0]
            bldg_cols = _detect_building_names(header)
            if not bldg_cols:
                continue

            for ci, name in bldg_cols.items():
                if not any(b.name == name for b in buildings):
                    b = BuildingArea(name=name)
                    b.summary_page = pidx
                    buildings.append(b)

            in_subitem = False
            current_far_cat = None
            current_sub_label = None
            for row in data[1:]:
                row_texts = [_row_str(row, ci) for ci in range(len(row))]
                row_joined = " ".join(row_texts)

                # "分项面积"行可能同时包含第一个分项数据（主要功能+厂房+许可+值）
                # 不能直接continue跳过
                if "分项" in row_joined and "面积" in row_joined:
                    in_subitem = True
                    current_sub_label = None
                    # 不continue，继续处理该行的数据
                if "计容面积" in row_joined and "分项" not in row_joined:
                    in_subitem = False
                    current_far_cat = "far"
                    current_sub_label = None
                elif "基底面积" in row_joined:
                    in_subitem = False
                    current_far_cat = "base"
                    current_sub_label = None
                elif "主要功能" in row_joined:
                    current_sub_label = "主要功能"
                elif "其它项目" in row_joined or "其他项目" in row_joined:
                    current_sub_label = "其他项目"

                sub = _detect_sub_type(row_joined)
                if not sub:
                    continue

                sub_label = ""
                for ci in range(len(row)):
                    cell = _row_str(row, ci)
                    if not cell:
                        continue
                    if cell in ("许可", "测量", "饰面"):
                        continue
                    if ci in bldg_cols:
                        continue
                    cell_clean = cell.replace('\n', '').replace(' ', '')
                    if cell_clean in ("主要功能", "其它项目", "其他项目", "分项面积"):
                        continue
                    if re.match(r'^[\d.]+$', cell):
                        continue
                    sub_label = cell_clean
                    break

                if sub_label:
                    current_sub_label = sub_label
                else:
                    sub_label = current_sub_label or ""

                if in_subitem:
                    for ci, bldg_name in bldg_cols.items():
                        val_str = _row_str(row, ci)
                        if not val_str:
                            continue
                        num_val = d(val_str)
                        if num_val is None:
                            continue

                        bld = next((b for b in buildings if b.name == bldg_name), None)
                        if not bld:
                            continue

                        item_label = sub_label or "未命名分项"
                        item_key = re.sub(r"\s+", "", item_label.replace("\n", ""))
                        if not item_key or item_key in {"分项面积", "小计", "合计", "总计"}:
                            continue
                        item = bld.far_subitems.setdefault(item_key, AreaItem())
                        old_value = getattr(item, sub)
                        setattr(item, sub, num_val if old_value is None else old_value + num_val)

                    continue

                for ci, bldg_name in bldg_cols.items():
                    val_str = _row_str(row, ci)
                    if not val_str:
                        continue
                    num_val = d(val_str)
                    if num_val is None:
                        continue

                    bld = next((b for b in buildings if b.name == bldg_name), None)
                    if not bld:
                        continue

                    if current_far_cat == "base":
                        setattr(bld.base_area, sub, num_val)
                    elif current_far_cat == "far":
                        setattr(bld.far_area, sub, num_val)

    # "分项面积"重命名同样适用于计容面积分项
    for bld in buildings:
        if "分项面积" in bld.far_subitems and "主要功能" not in bld.far_subitems:
            item = bld.far_subitems.pop("分项面积")
            bld.far_subitems["主要功能"] = item

    return buildings


def parse_planning_indicators(doc):
    indicators = PlanningIndicators()

    page_idxs = _find_pages(doc, "规划条件核实指标", start=3)
    for pidx in page_idxs:
        if not _is_table_page(doc, pidx):
            continue
        tables = _get_tables(doc, pidx)
        for tab in tables:
            data = tab.extract()
            for row in data:
                row_joined = " ".join(str(c).strip() if c else "" for c in row)
                cells = [str(c).strip() if c else "" for c in row]
                nums = [d(c) for c in cells if d(c) is not None]

                if "建筑基底面积" in row_joined and len(nums) >= 2:
                    indicators.base_area_permit = nums[0]
                    indicators.base_area_measure = nums[1]
                    indicators.indicator_page = pidx
                elif "建筑基底面积" in row_joined and len(nums) == 1:
                    indicators.base_area_measure = nums[0]
                    indicators.indicator_page = pidx

                elif "总建筑面积" in row_joined and "计容" not in row_joined:
                    if len(nums) >= 2:
                        indicators.total_area_permit = nums[0]
                        indicators.total_area_measure = nums[1]
                    elif len(nums) == 1:
                        indicators.total_area_measure = nums[0]
                    if indicators.indicator_page < 0:
                        indicators.indicator_page = pidx

                elif "总计容面积" in row_joined:
                    if len(nums) >= 2:
                        indicators.total_FAR_area_permit = nums[0]
                        indicators.total_FAR_area_measure = nums[1]
                    elif len(nums) == 1:
                        indicators.total_FAR_area_measure = nums[0]

                elif "绿化面积" in row_joined and len(nums) >= 2:
                    indicators.green_area_permit = nums[0]
                    indicators.green_area_measure = nums[1]

                elif "可确权" in row_joined and nums:
                    indicators.certifiable_area = nums[0]
                elif "不可确权" in row_joined and nums:
                    indicators.non_certifiable_area = nums[0]

                elif "不动产" in row_joined and "总建筑面积" in row_joined and nums:
                    indicators.real_estate_total_area = nums[0]

    if indicators.total_area_measure is None:
        for pidx in page_idxs:
            text = doc[pidx].get_text()
            for line in text.split('\n'):
                if "总建筑面积" in line and "计容" not in line:
                    nums = re.findall(r'[\d.]+', line)
                    if len(nums) >= 2:
                        indicators.total_area_permit = d(nums[0])
                        indicators.total_area_measure = d(nums[1])
                    break

    overview_idxs = _find_pages(doc, "面积汇总概况", start=3)
    for pidx in overview_idxs:
        if not _is_table_page(doc, pidx):
            continue
        indicators.overview_page = pidx

    return indicators


def _parse_floor_detail_row(cells, existing, current_floor_ref):
    """解析分层面积表明细行（通用格式）"""
    col0 = cells[0] if cells else ""
    col1 = cells[1] if len(cells) > 1 else ""

    floor_m = re.match(r'^(-?\d+)\s*层$', col0.strip())
    if floor_m:
        floor_name = f"{floor_m.group(1)}层"
        current_floor_ref[0] = next(
            (f for f in existing.floors if f.floor_name == floor_name), None)
        if not current_floor_ref[0]:
            current_floor_ref[0] = FloorArea(floor_name=floor_name)
            existing.floors.append(current_floor_ref[0])
        return

    if any(k in col0 for k in ["天面", "屋面", "屋顶"]):
        floor_name = col0.strip() if col0.strip() else "天面层"
        current_floor_ref[0] = next(
            (f for f in existing.floors if f.floor_name == floor_name), None)
        if not current_floor_ref[0]:
            current_floor_ref[0] = FloorArea(floor_name=floor_name)
            existing.floors.append(current_floor_ref[0])
        return

    if "总" in col0 and ("面积" in col0 or "建筑" in col0 or "公建" in col0 or "套内" in col0 or "车间" in col0):
        nums = [d(c) for c in cells[1:] if d(c) is not None]
        if nums:
            label_clean = col0.replace('\n', '').replace(' ', '')
            if "车间" in label_clean and existing.total_workshop is None:
                existing.total_workshop = nums[0]
            elif "套内" in label_clean and existing.total_inner is None:
                existing.total_inner = nums[0]
            elif "公建" in label_clean and "分摊" in label_clean and existing.total_shared_public is None:
                existing.total_shared_public = nums[0]
            elif "公建" in label_clean and "不分摊" in label_clean and existing.total_unshared_public is None:
                existing.total_unshared_public = nums[0]
            elif "建筑" in label_clean and existing.total_building is None:
                existing.total_building = nums[0]
        return

    if current_floor_ref[0] and len(cells) >= 3:
        label = col1
        nums = [d(c) for c in cells[2:] if d(c) is not None]
        val = nums[0] if nums else None
        if val is None and len(cells) >= 2:
            nums_alt = [d(c) for c in cells[1:] if d(c) is not None]
            val = nums_alt[0] if nums_alt else None
            if val and not label:
                return

        if not label or not val:
            return

        label_clean = label.replace('\n', '').replace(' ', '')
        if "不分摊" in label_clean:
            current_floor_ref[0].unshared_public_area = val
        elif "公建" in label_clean or "公共" in label_clean:
            current_floor_ref[0].public_area = val
        elif "车间" in label_clean or "套内" in label_clean:
            current_floor_ref[0].workshop_area = val
        else:
            area_name = label_clean.replace("面积", "")
            if any(k in area_name for k in ["办公", "宿舍", "教室", "教育", "车间", "停车", "车位", "商业", "住宅", "设备"]):
                if current_floor_ref[0].workshop_area is None:
                    current_floor_ref[0].workshop_area = val
                else:
                    current_floor_ref[0].workshop_area += val
            elif any(k in area_name for k in ["走廊", "楼梯", "电梯", "门厅", "大堂", "公"]):
                if current_floor_ref[0].public_area is None:
                    current_floor_ref[0].public_area = val
                else:
                    current_floor_ref[0].public_area += val


def parse_floor_area_tables(doc):
    tables = []

    # 分层汇总表
    summary_idxs = []
    for i in range(3, len(doc)):
        text = doc[i].get_text()
        if "分层汇总表" in text:
            summary_idxs.append(i)

    for pidx in summary_idxs:
        page_text = doc[pidx].get_text()
        bldg_name = _extract_building_name_from_page(page_text)
        if not bldg_name:
            continue

        table = FloorAreaTable(building_name=bldg_name, summary_page=pidx)
        page_tables = _get_tables(doc, pidx)
        for tab in page_tables:
            data = tab.extract()
            for row in data:
                cells = [str(c).strip() if c else "" for c in row]
                label = cells[0] if cells else ""
                nums = [d(c) for c in cells[1:] if d(c) is not None]
                val = nums[0] if nums else None

                label_clean = label.replace('\n', '').replace(' ', '')
                if "总车间" in label_clean:
                    table.total_workshop = val
                elif "总套内" in label_clean:
                    table.total_inner = val
                elif "总分摊公建" in label_clean:
                    table.total_shared_public = val
                elif "总不分摊" in label_clean:
                    table.total_unshared_public = val
                elif "总公建" in label_clean and "分摊" not in label_clean and "不分摊" not in label_clean:
                    table.total_public = val
                elif "总建筑面积" in label_clean:
                    table.total_building = val
                elif "预留" in label_clean:
                    table.reserved_inner = val

        existing = next((t for t in tables if t.building_name == table.building_name), None)
        if existing:
            for attr in ["total_workshop", "total_inner", "total_shared_public",
                         "total_unshared_public", "total_public", "total_building",
                         "reserved_inner"]:
                val = getattr(table, attr)
                if val is not None:
                    setattr(existing, attr, val)
            existing.summary_page = pidx
        else:
            tables.append(table)

    # 分层面积表（明细）
    detail_idxs = []
    for i in range(3, len(doc)):
        text = doc[i].get_text()
        if "分层面积表" in text or "房产分层面积" in text:
            detail_idxs.append(i)

    for pidx in detail_idxs:
        page_text = doc[pidx].get_text()
        bldg_name = _extract_building_name_from_page(page_text)
        if not bldg_name:
            continue

        existing = next((t for t in tables if t.building_name == bldg_name), None)
        if not existing:
            existing = FloorAreaTable(building_name=bldg_name)
            tables.append(existing)
        existing.detail_page = pidx

        current_floor_ref = [None]
        page_tables = _get_tables(doc, pidx)
        for tab in page_tables:
            data = tab.extract()
            for row in data:
                cells = [str(c).strip() if c else "" for c in row]
                _parse_floor_detail_row(cells, existing, current_floor_ref)

        for offset in range(1, 3):
            next_pidx = pidx + offset
            if next_pidx >= len(doc):
                break
            next_text = doc[next_pidx].get_text()
            if "分层汇总表" in next_text or "分层面积表" in next_text or "房产分层面积" in next_text:
                break
            if "总" in next_text and "面积" in next_text and "目录" not in next_text:
                page_tables = _get_tables(doc, next_pidx)
                for tab in page_tables:
                    data = tab.extract()
                    for row in data:
                        cells = [str(c).strip() if c else "" for c in row]
                        _parse_floor_detail_row(cells, existing, current_floor_ref)

    return tables


def _extract_building_name_from_page(page_text):
    """从页面文本中提取建筑名称"""
    # 优先识别"新智园X栋/幢"等通用栋号模式
    m = re.search(r'(新智园\s*\d+\s*栋)', page_text)
    if m:
        return m.group(1).replace(' ', '')
    m = re.search(r'([\u4e00-\u9fa5]{1,6}\d+栋)', page_text)
    if m:
        return m.group(1)
    name_patterns = [
        r'(厂房[一二三四五六七八九十]+)',
        r'(地下室)',
        r'(地下车库)',
        r'(教学楼)',
        r'(体育馆)',
        r'(行政楼)',
        r'(宿舍楼)',
        r'(宿舍综合楼)',
        r'(宿舍)',
        r'(综合楼)',
        r'(停车库)',
        r'(停车楼)',
        r'(通讯基站)',
        r'(商业楼)',
        r'(住宅楼)',
        r'(办公楼)',
    ]
    for pattern in name_patterns:
        m = re.search(pattern, page_text)
        if m:
            return m.group(1)

    for line in page_text.split('\n'):
        line = line.strip()
        if not line or len(line) > 10:
            continue
        if re.match(r'^(厂房|地下|教学|体育|行政|宿舍|综合|停车|通讯|商业|住宅|办公|车间|配电|消防)', line):
            cleaned = re.sub(r'[\d\s页]', '', line)
            if cleaned and len(cleaned) <= 8:
                return cleaned
    return ""


def _extract_building_name_from_title(text):
    """从表格标题行提取建筑名称（如'厂房二分摊说明'→'厂房二'）"""
    # 优先识别"新智园X栋分摊"模式
    m = re.search(r'(新智园\s*\d+\s*栋)\s*分摊', text)
    if m:
        return m.group(1).replace(' ', '')
    m = re.search(r'([\u4e00-\u9fa5]{1,6}\d+栋)\s*分摊', text)
    if m:
        return m.group(1)
    patterns = [
        r'(厂房[一二三四五六七八九十]+)分摊',
        r'(地下室)分摊',
        r'(地下车库)分摊',
        r'(教学楼)分摊',
        r'(体育馆)分摊',
        r'(行政楼)分摊',
        r'(宿舍楼)分摊',
        r'(宿舍综合楼)分摊',
        r'(宿舍)分摊',
        r'(综合楼)分摊',
        r'(停车库)分摊',
        r'(停车楼)分摊',
        r'(商业楼)分摊',
        r'(住宅楼)分摊',
        r'(办公楼)分摊',
        r'(连廊)分摊',
        r'(门卫室)分摊',
        r'(配电房)分摊',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return _extract_building_name_from_page(text)


def parse_apportionment_info(doc):
    results = []
    page_idxs = set()
    for kw in ["分摊说明", "功能区分摊说明"]:
        for i in range(3, len(doc)):
            if doc[i].search_for(kw):
                page_idxs.add(i)
    page_idxs = sorted(page_idxs)

    current_building = None

    for pidx in page_idxs:
        if not _is_table_page(doc, pidx, exclude_keywords=["目录"]):
            continue

        tables = _get_tables(doc, pidx)

        for tab in tables:
            data = tab.extract()
            if not data:
                continue

            table_building = ""
            for row in data[:3]:
                for cell in row:
                    if cell:
                        cell_str = str(cell)
                        if "分摊" in cell_str or "厂房" in cell_str or "地下" in cell_str:
                            table_building = _extract_building_name_from_title(cell_str)
                            if table_building:
                                break
                if table_building:
                    break

            if table_building:
                current_building = table_building
            elif current_building is None:
                continue

            building_name = current_building

            is_tree_table = False
            for row in data[:5]:
                row_joined = " ".join(str(c).strip() if c else "" for c in row)
                if "分摊树" in row_joined:
                    is_tree_table = True
                    break

            if is_tree_table:
                continue

            info = next((r for r in results if r.building_name == building_name), None)
            if not info:
                info = ApportionmentInfo(building_name=building_name, page=pidx)
                results.append(info)
            else:
                info.page = pidx

            in_main_zone = False
            in_summary = False
            in_sources = False

            for row in data:
                cells = [str(c).strip() if c else "" for c in row]
                row_joined = " ".join(cells)

                if "功能区分摊说明汇总" in row_joined:
                    in_summary = True
                    in_main_zone = False
                    in_sources = False
                    continue

                if "功能区分摊说明" in row_joined and "汇总" not in row_joined:
                    in_summary = False
                    in_main_zone = False
                    in_sources = False

                if "功能名称" in row_joined:
                    cell_joined = row_joined.replace('\n', '').replace(' ', '')
                    if "1()" in cell_joined:
                        in_main_zone = True
                        in_sources = False
                    elif "不摊" in cell_joined:
                        in_main_zone = False
                        in_sources = False

                if "分摊面积来源" in row_joined or "分摊来源" in row_joined:
                    in_sources = True
                    continue

                if in_main_zone and not in_summary and not in_sources:
                    if "分摊系数" in row_joined:
                        for ci, cell in enumerate(cells):
                            if "分摊系数" in cell:
                                for offset in range(1, 3):
                                    if ci + offset < len(cells):
                                        val = d(cells[ci + offset])
                                        if val is not None:
                                            info.coefficient = val
                                            break

                    for ci, cell in enumerate(cells):
                        cell_clean = cell.replace('\n', '').replace(' ', '')
                        if "总套内建筑" in cell_clean and ci + 1 < len(cells):
                            val = d(cells[ci + 1])
                            if val is not None:
                                info.total_inner = val
                        if "总分摊" in cell_clean and "建筑面积" in cell_clean and ci + 1 < len(cells):
                            val = d(cells[ci + 1])
                            if val is not None:
                                info.total_shared = val
                        if "总建筑面积" in cell_clean and "分摊" not in cell_clean and ci + 1 < len(cells):
                            val = d(cells[ci + 1])
                            if val is not None:
                                info.total_building = val

                if in_sources and not in_summary:
                    if "功能名称" in row_joined or "功能区分摊" in row_joined:
                        in_sources = False
                    elif len(cells) >= 5:
                        name = cells[2] if cells[2] and not d(cells[2]) else ""
                        area_val = None
                        for ci in range(3, len(cells)):
                            v = d(cells[ci])
                            if v is not None:
                                area_val = v
                                break
                        if area_val is not None and name:
                            info.sources.append(ApportionmentSource(name=name, area=area_val))

                if in_summary:
                    if "功能区名称" in row_joined or "功能用途" in row_joined:
                        continue
                    if cells[0].strip().isdigit() and len(cells) > 4:
                        if info.summary_inner is None:
                            info.summary_building = d(cells[2])
                            info.summary_inner = d(cells[3])
                            info.summary_shared = d(cells[4])

    return results


def parse_unit_area_tables(doc):
    tables = []
    for ap in parse_apportionment_info(doc):
        if ap.total_inner is not None or ap.total_shared is not None:
            ut = UnitAreaTable(
                building_name=ap.building_name,
                total_inner=ap.total_inner,
                total_shared=ap.total_shared,
            )
            tables.append(ut)
    return tables


def parse_pdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    report = ReportData(pdf_path=pdf_path, total_pages=len(doc))

    report.buildings = parse_building_area_summary(doc)
    report.floor_tables = parse_floor_area_tables(doc)
    report.apportionments = parse_apportionment_info(doc)
    report.unit_tables = parse_unit_area_tables(doc)
    report.planning = parse_planning_indicators(doc)

    doc.close()
    return report
