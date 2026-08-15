from decimal import Decimal
from models import CheckResult, TOL

FLOOR_TOL = Decimal("0.5")


def _approx_eq(a, b, tol=TOL):
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def _fmt(val):
    if val is None:
        return "缺失"
    return f"{val:.2f}"


def _fmt_parts(parts):
    """格式化加法算式，如 '25070.39 + 231.52 + 92.02'"""
    return " + ".join(_fmt(p) for p in parts)


def check_vertical(report):
    results = []

    # ===== 建筑面积汇总表：分项合计 = 总面积 =====
    for b in report.buildings:
        # --- 测量值 ---
        sub_measured = b.subitem_sum_measured()
        if sub_measured is not None and b.total_area.measured is not None:
            parts = []
            if b.main_function.measured is not None:
                parts.append(("主要功能", b.main_function.measured))
            if b.roof_stair.measured is not None:
                parts.append(("屋面梯屋", b.roof_stair.measured))
            if b.facility.measured is not None:
                parts.append(("配套设施", b.facility.measured))
            if b.basement.measured is not None:
                parts.append(("地下室", b.basement.measured))

            calc_str = " + ".join(f"{name}({_fmt(val)})" for name, val in parts)
            calc_str += f" = {_fmt(sub_measured)}"

            if _approx_eq(sub_measured, b.total_area.measured):
                results.append(CheckResult(
                    "竖向-建筑面积汇总表", f"{b.name} 分项合计(测量)=总面积(测量)",
                    "pass", _fmt(b.total_area.measured), _fmt(sub_measured),
                    f"差额 0.00㎡，分项合计={_fmt(sub_measured)}，总面积={_fmt(b.total_area.measured)}",
                    f"建筑面积汇总表 {b.name}", b.summary_page,
                    calc_process=calc_str))
            else:
                diff = sub_measured - b.total_area.measured
                results.append(CheckResult(
                    "竖向-建筑面积汇总表", f"{b.name} 分项合计(测量)≠总面积(测量)",
                    "fail", _fmt(b.total_area.measured), _fmt(sub_measured),
                    f"差额 {diff:+.2f}㎡，分项合计={_fmt(sub_measured)}，总面积={_fmt(b.total_area.measured)}",
                    f"建筑面积汇总表 {b.name}", b.summary_page,
                    calc_process=calc_str + f" ≠ 总面积({_fmt(b.total_area.measured)})"))

        # --- 许可值 ---
        sub_permitted = b.subitem_sum_permitted()
        if sub_permitted is not None and b.total_area.permitted is not None:
            parts = []
            if b.main_function.permitted is not None:
                parts.append(("主要功能", b.main_function.permitted))
            if b.roof_stair.permitted is not None:
                parts.append(("屋面梯屋", b.roof_stair.permitted))
            if b.facility.permitted is not None:
                parts.append(("配套设施", b.facility.permitted))
            if b.basement.permitted is not None:
                parts.append(("地下室", b.basement.permitted))

            calc_str = " + ".join(f"{name}({_fmt(val)})" for name, val in parts)
            calc_str += f" = {_fmt(sub_permitted)}"

            if not _approx_eq(sub_permitted, b.total_area.permitted):
                diff = sub_permitted - b.total_area.permitted
                results.append(CheckResult(
                    "竖向-建筑面积汇总表", f"{b.name} 分项合计(许可)≠总面积(许可)",
                    "fail", _fmt(b.total_area.permitted), _fmt(sub_permitted),
                    f"差额 {diff:+.2f}㎡",
                    f"建筑面积汇总表 {b.name}", b.summary_page,
                    calc_process=calc_str + f" ≠ 总面积许可({_fmt(b.total_area.permitted)})"))
            else:
                results.append(CheckResult(
                    "竖向-建筑面积汇总表", f"{b.name} 分项合计(许可)=总面积(许可)",
                    "pass", _fmt(b.total_area.permitted), _fmt(sub_permitted),
                    f"差额 0.00㎡",
                    f"建筑面积汇总表 {b.name}", b.summary_page,
                    calc_process=calc_str + f" = 总面积许可({_fmt(b.total_area.permitted)})"))

        # --- 计容面积 ---
        if b.far_area.measured is not None:
            far_sub = b.far_subitem_sum_measured()
            if far_sub is not None:
                parts = []
                if b.main_function.measured is not None:
                    parts.append(("主要功能", b.main_function.measured))
                if b.facility.measured is not None:
                    parts.append(("配套设施", b.facility.measured))
                calc_str = " + ".join(f"{name}({_fmt(val)})" for name, val in parts)
                calc_str += f" = {_fmt(far_sub)}"

                if not _approx_eq(far_sub, b.far_area.measured):
                    diff = far_sub - b.far_area.measured
                    results.append(CheckResult(
                        "竖向-计容面积汇总表", f"{b.name} 分项合计(测量)≠计容面积(测量)",
                        "fail", _fmt(b.far_area.measured), _fmt(far_sub),
                        f"差额 {diff:+.2f}㎡",
                        f"计容面积汇总表 {b.name}", b.summary_page,
                        calc_process=calc_str + f" ≠ 计容面积({_fmt(b.far_area.measured)})"))
                else:
                    results.append(CheckResult(
                        "竖向-计容面积汇总表", f"{b.name} 分项合计(测量)=计容面积(测量)",
                        "pass", _fmt(b.far_area.measured), _fmt(far_sub),
                        f"差额 0.00㎡",
                        f"计容面积汇总表 {b.name}", b.summary_page,
                        calc_process=calc_str + f" = 计容面积({_fmt(b.far_area.measured)})"))

    # ===== 分层面积表：逐层合计 = 总计 =====
    for ft in report.floor_tables:
        # --- 逐层车间面积 ---
        ws_sum = ft.floor_workshop_sum()
        if ws_sum is not None and ft.total_workshop is not None:
            floor_details = ", ".join(
                f"{f.floor_name}={_fmt(f.workshop_area)}"
                for f in ft.floors if f.workshop_area is not None
            )
            calc_str = f"逐层车间: {floor_details}\n合计 = {_fmt(ws_sum)}"

            if not _approx_eq(ws_sum, ft.total_workshop, tol=FLOOR_TOL):
                results.append(CheckResult(
                    "竖向-分层面积表", f"{ft.building_name} 逐层车间面积合计≠总车间面积",
                    "fail", _fmt(ft.total_workshop), _fmt(ws_sum),
                    f"逐层合计={_fmt(ws_sum)}, 报告总计={_fmt(ft.total_workshop)}",
                    f"分层面积表 {ft.building_name}", ft.detail_page,
                    calc_process=calc_str + f" ≠ 总车间({_fmt(ft.total_workshop)})"))
            else:
                results.append(CheckResult(
                    "竖向-分层面积表", f"{ft.building_name} 逐层车间面积合计=总车间面积",
                    "pass", _fmt(ft.total_workshop), _fmt(ws_sum),
                    f"逐层合计={_fmt(ws_sum)}, 报告总计={_fmt(ft.total_workshop)}",
                    f"分层面积表 {ft.building_name}", ft.detail_page,
                    calc_process=calc_str + f" = 总车间({_fmt(ft.total_workshop)})"))

        # --- 逐层公建面积 ---
        pub_sum = ft.floor_public_sum()
        if pub_sum is not None and ft.total_shared_public is not None:
            floor_details = ", ".join(
                f"{f.floor_name}={_fmt(f.public_area)}"
                for f in ft.floors if f.public_area is not None
            )
            calc_str = f"逐层公建: {floor_details}\n合计 = {_fmt(pub_sum)}"

            if not _approx_eq(pub_sum, ft.total_shared_public, tol=FLOOR_TOL):
                results.append(CheckResult(
                    "竖向-分层面积表", f"{ft.building_name} 逐层公建面积合计≠总分摊公建面积",
                    "fail", _fmt(ft.total_shared_public), _fmt(pub_sum),
                    f"逐层合计={_fmt(pub_sum)}, 报告分摊公建={_fmt(ft.total_shared_public)}",
                    f"分层面积表 {ft.building_name}", ft.detail_page,
                    calc_process=calc_str + f" ≠ 总分摊公建({_fmt(ft.total_shared_public)})"))
            else:
                results.append(CheckResult(
                    "竖向-分层面积表", f"{ft.building_name} 逐层公建面积合计=总分摊公建面积",
                    "pass", _fmt(ft.total_shared_public), _fmt(pub_sum),
                    f"逐层合计={_fmt(pub_sum)}, 报告分摊公建={_fmt(ft.total_shared_public)}",
                    f"分层面积表 {ft.building_name}", ft.detail_page,
                    calc_process=calc_str + f" = 总分摊公建({_fmt(ft.total_shared_public)})"))

        # --- 总套内 + 总公建 = 总建筑 ---
        if ft.total_inner is not None and ft.total_shared_public is not None and ft.total_building is not None:
            calc = ft.total_inner + ft.total_shared_public
            parts_str = f"套内({_fmt(ft.total_inner)}) + 分摊公建({_fmt(ft.total_shared_public)})"
            if ft.total_unshared_public is not None:
                calc += ft.total_unshared_public
                parts_str += f" + 不分摊公建({_fmt(ft.total_unshared_public)})"
            parts_str += f" = {_fmt(calc)}"

            if not _approx_eq(calc, ft.total_building, tol=FLOOR_TOL):
                results.append(CheckResult(
                    "竖向-分层面积表", f"{ft.building_name} 总套内+总公建≠总建筑面积",
                    "fail", _fmt(ft.total_building), _fmt(calc),
                    parts_str + f" ≠ 总建筑({_fmt(ft.total_building)})",
                    f"分层汇总表 {ft.building_name}", ft.summary_page,
                    calc_process=parts_str + f" ≠ 总建筑({_fmt(ft.total_building)})"))
            else:
                results.append(CheckResult(
                    "竖向-分层面积表", f"{ft.building_name} 总套内+总公建=总建筑面积",
                    "pass", _fmt(ft.total_building), _fmt(calc),
                    parts_str + f" = 总建筑({_fmt(ft.total_building)})",
                    f"分层汇总表 {ft.building_name}", ft.summary_page,
                    calc_process=parts_str + f" = 总建筑({_fmt(ft.total_building)})"))

    # ===== 分摊说明：总套内 + 总分摊 = 总建筑 =====
    for ap in report.apportionments:
        if ap.total_inner is not None and ap.total_shared is not None and ap.total_building is not None:
            calc = ap.total_inner + ap.total_shared
            calc_str = f"套内({_fmt(ap.total_inner)}) + 分摊({_fmt(ap.total_shared)}) = {_fmt(calc)}"

            if not _approx_eq(calc, ap.total_building, tol=FLOOR_TOL):
                results.append(CheckResult(
                    "竖向-分摊说明", f"{ap.building_name} 总套内+总分摊≠总建筑面积",
                    "fail", _fmt(ap.total_building), _fmt(calc),
                    calc_str + f" ≠ 总建筑({_fmt(ap.total_building)})",
                    page_num=ap.page, calc_process=calc_str + f" ≠ 总建筑({_fmt(ap.total_building)})"))
            else:
                results.append(CheckResult(
                    "竖向-分摊说明", f"{ap.building_name} 总套内+总分摊=总建筑面积",
                    "pass", _fmt(ap.total_building), _fmt(calc),
                    calc_str + f" = 总建筑({_fmt(ap.total_building)})",
                    page_num=ap.page, calc_process=calc_str + f" = 总建筑({_fmt(ap.total_building)})"))

        # --- 分摊来源明细 ---
        src_sum = ap.source_sum()
        if src_sum is not None and ap.total_shared is not None:
            src_details = ", ".join(f"{s.name}={_fmt(s.area)}" for s in ap.sources if s.area is not None)
            calc_str = f"来源明细: {src_details}\n合计 = {_fmt(src_sum)}"

            if not _approx_eq(src_sum, ap.total_shared, tol=FLOOR_TOL):
                results.append(CheckResult(
                    "竖向-分摊说明", f"{ap.building_name} 分摊来源明细合计≠总分摊面积",
                    "fail", _fmt(ap.total_shared), _fmt(src_sum),
                    calc_str + f" ≠ 总分摊({_fmt(ap.total_shared)})",
                    page_num=ap.page, calc_process=calc_str + f" ≠ 总分摊({_fmt(ap.total_shared)})"))
            else:
                results.append(CheckResult(
                    "竖向-分摊说明", f"{ap.building_name} 分摊来源明细合计=总分摊面积",
                    "pass", _fmt(ap.total_shared), _fmt(src_sum),
                    calc_str + f" = 总分摊({_fmt(ap.total_shared)})",
                    page_num=ap.page, calc_process=calc_str + f" = 总分摊({_fmt(ap.total_shared)})"))

        # --- 汇总行 ---
        if ap.summary_inner is not None and ap.summary_shared is not None and ap.summary_building is not None:
            calc = ap.summary_inner + ap.summary_shared
            calc_str = f"汇总套内({_fmt(ap.summary_inner)}) + 汇总分摊({_fmt(ap.summary_shared)}) = {_fmt(calc)}"

            if not _approx_eq(calc, ap.summary_building, tol=FLOOR_TOL):
                results.append(CheckResult(
                    "竖向-分摊说明汇总", f"{ap.building_name} 汇总套内+汇总分摊≠汇总建筑",
                    "fail", _fmt(ap.summary_building), _fmt(calc),
                    calc_str + f" ≠ 汇总建筑({_fmt(ap.summary_building)})",
                    page_num=ap.page, calc_process=calc_str + f" ≠ 汇总建筑({_fmt(ap.summary_building)})"))

    return results


def check_horizontal(report):
    results = []

    for ft in report.floor_tables:
        # --- 分层表 vs 单元表 ---
        ut = next((u for u in report.unit_tables if u.building_name == ft.building_name), None)
        if ut:
            if ft.total_inner is not None and ut.total_inner is not None:
                calc_str = f"分层表总套内={_fmt(ft.total_inner)} vs 单元表套内合计={_fmt(ut.total_inner)}"
                if not _approx_eq(ft.total_inner, ut.total_inner, tol=FLOOR_TOL):
                    results.append(CheckResult(
                        "横向-分层vs单元", f"{ft.building_name} 分层总套内≠单元套内合计",
                        "fail", _fmt(ft.total_inner), _fmt(ut.total_inner),
                        calc_str, page_num=ft.summary_page, calc_process=calc_str))
                else:
                    results.append(CheckResult(
                        "横向-分层vs单元", f"{ft.building_name} 分层总套内=单元套内合计",
                        "pass", _fmt(ft.total_inner), _fmt(ut.total_inner),
                        calc_str, page_num=ft.summary_page, calc_process=calc_str))

            if ft.total_shared_public is not None and ut.total_shared is not None:
                calc_str = f"分层表总分摊公建={_fmt(ft.total_shared_public)} vs 单元表分摊合计={_fmt(ut.total_shared)}"
                if not _approx_eq(ft.total_shared_public, ut.total_shared, tol=FLOOR_TOL):
                    results.append(CheckResult(
                        "横向-分层vs单元", f"{ft.building_name} 分层总分摊公建≠单元分摊合计",
                        "fail", _fmt(ft.total_shared_public), _fmt(ut.total_shared),
                        calc_str, page_num=ft.summary_page, calc_process=calc_str))
                else:
                    results.append(CheckResult(
                        "横向-分层vs单元", f"{ft.building_name} 分层总分摊公建=单元分摊合计",
                        "pass", _fmt(ft.total_shared_public), _fmt(ut.total_shared),
                        calc_str, page_num=ft.summary_page, calc_process=calc_str))

        # --- 分层表 vs 汇总表 ---
        bld = next((b for b in report.buildings if b.name == ft.building_name), None)
        if bld and ft.total_building is not None and bld.total_area.measured is not None:
            measured_val = bld.total_area.measured
            finishing_val = bld.total_area.finishing
            expected = measured_val
            calc_str = f"汇总表测量({_fmt(measured_val)})"
            if finishing_val is not None:
                expected += finishing_val
                calc_str += f" + 饰面({_fmt(finishing_val)})"
            calc_str += f" = {_fmt(expected)} vs 分层总建筑({_fmt(ft.total_building)})"

            if not _approx_eq(ft.total_building, expected, tol=FLOOR_TOL):
                results.append(CheckResult(
                    "横向-分层vs汇总表", f"{ft.building_name} 分层总面积≠汇总表(测量+饰面)",
                    "fail", _fmt(expected), _fmt(ft.total_building),
                    calc_str, page_num=bld.summary_page, calc_process=calc_str))
            else:
                results.append(CheckResult(
                    "横向-分层vs汇总表", f"{ft.building_name} 分层总面积=汇总表(测量+饰面)",
                    "pass", _fmt(expected), _fmt(ft.total_building),
                    calc_str, page_num=bld.summary_page, calc_process=calc_str))

        # --- 分摊说明 vs 分层表 ---
        ap = next((a for a in report.apportionments if a.building_name == ft.building_name), None)
        if ap:
            compare_inner = ap.summary_inner if ap.summary_inner is not None else ap.total_inner
            compare_shared = ap.summary_shared if ap.summary_shared is not None else ap.total_shared
            compare_building = ap.summary_building if ap.summary_building is not None else ap.total_building

            if compare_inner is not None and ft.total_inner is not None:
                calc_str = f"分摊说明套内={_fmt(compare_inner)} vs 分层表套内={_fmt(ft.total_inner)}"
                if not _approx_eq(compare_inner, ft.total_inner, tol=FLOOR_TOL):
                    results.append(CheckResult(
                        "横向-分摊说明vs分层", f"{ft.building_name} 分摊说明总套内≠分层总套内",
                        "fail", _fmt(ft.total_inner), _fmt(compare_inner),
                        calc_str, page_num=ap.page, calc_process=calc_str))
                else:
                    results.append(CheckResult(
                        "横向-分摊说明vs分层", f"{ft.building_name} 分摊说明总套内=分层总套内",
                        "pass", _fmt(ft.total_inner), _fmt(compare_inner),
                        calc_str, page_num=ap.page, calc_process=calc_str))

            if compare_shared is not None and ft.total_shared_public is not None:
                calc_str = f"分摊说明分摊={_fmt(compare_shared)} vs 分层表分摊公建={_fmt(ft.total_shared_public)}"
                if not _approx_eq(compare_shared, ft.total_shared_public, tol=FLOOR_TOL):
                    results.append(CheckResult(
                        "横向-分摊说明vs分层", f"{ft.building_name} 分摊说明总分摊≠分层总分摊公建",
                        "fail", _fmt(ft.total_shared_public), _fmt(compare_shared),
                        calc_str, page_num=ap.page, calc_process=calc_str))
                else:
                    results.append(CheckResult(
                        "横向-分摊说明vs分层", f"{ft.building_name} 分摊说明总分摊=分层总分摊公建",
                        "pass", _fmt(ft.total_shared_public), _fmt(compare_shared),
                        calc_str, page_num=ap.page, calc_process=calc_str))

            if compare_building is not None and ft.total_building is not None:
                expected_building = compare_building
                calc_str = f"分摊说明总建筑={_fmt(compare_building)}"
                if ft.total_unshared_public is not None:
                    expected_building += ft.total_unshared_public
                    calc_str += f" + 不分摊公建({_fmt(ft.total_unshared_public)})"
                calc_str += f" = {_fmt(expected_building)} vs 分层总建筑={_fmt(ft.total_building)}"
                if not _approx_eq(expected_building, ft.total_building, tol=FLOOR_TOL):
                    results.append(CheckResult(
                        "横向-分摊说明vs分层", f"{ft.building_name} 分摊说明总建筑+不分摊公建≠分层总建筑",
                        "warning", _fmt(ft.total_building), _fmt(expected_building),
                        calc_str, page_num=ap.page, calc_process=calc_str))

    # --- 各栋合计 vs 规划指标 ---
    building_total = Decimal("0")
    building_far = Decimal("0")
    building_details = []
    far_details = []
    for b in report.buildings:
        if b.total_area.measured is not None:
            building_total += b.total_area.measured
            building_details.append(f"{b.name}={_fmt(b.total_area.measured)}")
        if b.far_area.measured is not None:
            building_far += b.far_area.measured
            far_details.append(f"{b.name}={_fmt(b.far_area.measured)}")

    p = report.planning
    if p and p.total_area_measure is not None and building_total > 0:
        calc_str = f"各栋面积: {', '.join(building_details)}\n合计 = {_fmt(building_total)} vs 规划指标={_fmt(p.total_area_measure)}"
        if not _approx_eq(building_total, p.total_area_measure, tol=FLOOR_TOL):
            results.append(CheckResult(
                "横向-汇总表vs指标", "各建筑总面积合计≠规划指标总建筑面积",
                "fail", _fmt(p.total_area_measure), _fmt(building_total),
                calc_str, page_num=p.indicator_page, calc_process=calc_str))
        else:
            results.append(CheckResult(
                "横向-汇总表vs指标", "各建筑总面积合计=规划指标总建筑面积",
                "pass", _fmt(p.total_area_measure), _fmt(building_total),
                calc_str, page_num=p.indicator_page, calc_process=calc_str))

    if p and p.total_FAR_area_measure is not None and building_far > 0:
        calc_str = f"各栋计容: {', '.join(far_details)}\n合计 = {_fmt(building_far)} vs 规划指标={_fmt(p.total_FAR_area_measure)}"
        if not _approx_eq(building_far, p.total_FAR_area_measure, tol=FLOOR_TOL):
            results.append(CheckResult(
                "横向-汇总表vs指标", "各建筑计容面积合计≠规划指标总计容面积",
                "fail", _fmt(p.total_FAR_area_measure), _fmt(building_far),
                calc_str, page_num=p.indicator_page, calc_process=calc_str))
        else:
            results.append(CheckResult(
                "横向-汇总表vs指标", "各建筑计容面积合计=规划指标总计容面积",
                "pass", _fmt(p.total_FAR_area_measure), _fmt(building_far),
                calc_str, page_num=p.indicator_page, calc_process=calc_str))

    return results


def check_apportionment(report):
    results = []

    for ap in report.apportionments:
        compare_inner = ap.summary_inner if ap.summary_inner is not None else ap.total_inner
        compare_shared = ap.summary_shared if ap.summary_shared is not None else ap.total_shared

        if ap.coefficient is not None and compare_inner is not None and compare_shared is not None:
            if compare_inner > 0:
                calc_coeff = compare_shared / compare_inner
                calc_str = (f"总分摊({_fmt(compare_shared)}) ÷ 总套内({_fmt(compare_inner)})"
                           f" = {calc_coeff:.10f}")
                calc_str += f"\n报告系数 = {ap.coefficient:.10f}"

                if abs(calc_coeff - ap.coefficient) > Decimal("0.001"):
                    results.append(CheckResult(
                        "分摊系数", f"{ap.building_name} 分摊系数≠总分摊/总套内",
                        "fail", f"{ap.coefficient:.10f}", f"{calc_coeff:.10f}",
                        calc_str, page_num=ap.page, calc_process=calc_str))
                else:
                    results.append(CheckResult(
                        "分摊系数", f"{ap.building_name} 分摊系数=总分摊/总套内",
                        "pass", f"{ap.coefficient:.10f}", f"{calc_coeff:.10f}",
                        calc_str, page_num=ap.page, calc_process=calc_str))

    return results


def check_permitted_vs_measured(report):
    """检查许可值与测量值的一致性"""
    results = []
    WARN_ABS = Decimal("50")
    WARN_PCT = Decimal("1")
    ERROR_ABS = Decimal("200")
    ERROR_PCT = Decimal("5")

    for b in report.buildings:
        items = [
            ("总建筑面积", b.total_area),
            ("主要功能", b.main_function),
            ("屋面梯屋", b.roof_stair),
            ("配套设施", b.facility),
            ("地下室", b.basement),
        ]

        for item_name, item in items:
            if item.permitted is not None and item.measured is not None:
                if item.permitted == 0 and item.measured == 0:
                    continue
                diff = item.permitted - item.measured
                abs_diff = abs(diff)
                pct = (abs_diff / item.measured * 100) if item.measured > 0 else 0

                is_error = abs_diff >= ERROR_ABS and pct >= ERROR_PCT
                is_warn = abs_diff >= WARN_ABS and pct >= WARN_PCT

                if is_error:
                    calc_str = (f"许可({_fmt(item.permitted)}) - 测量({_fmt(item.measured)})"
                               f" = 差额({diff:+.2f}㎡, {pct:.1f}%)")
                    results.append(CheckResult(
                        "许可vs测量", f"{b.name} {item_name}许可值与测量值差异过大",
                        "fail", _fmt(item.measured), _fmt(item.permitted),
                        f"差额 {diff:+.2f}㎡ ({pct:.1f}%)，许可值与测量值应接近一致",
                        f"建筑面积汇总表 {b.name}", b.summary_page,
                        calc_process=calc_str))
                elif is_warn:
                    calc_str = (f"许可({_fmt(item.permitted)}) - 测量({_fmt(item.measured)})"
                               f" = 差额({diff:+.2f}㎡, {pct:.1f}%)")
                    results.append(CheckResult(
                        "许可vs测量", f"{b.name} {item_name}许可值与测量值存在差异",
                        "warning", _fmt(item.measured), _fmt(item.permitted),
                        f"差额 {diff:+.2f}㎡ ({pct:.1f}%)，建议核实许可值与测量值差异原因",
                        f"建筑面积汇总表 {b.name}", b.summary_page,
                        calc_process=calc_str))
                else:
                    calc_str = (f"许可({_fmt(item.permitted)}) - 测量({_fmt(item.measured)})"
                               f" = 差额({diff:+.2f}㎡, {pct:.1f}%)")
                    results.append(CheckResult(
                        "许可vs测量", f"{b.name} {item_name}许可值≈测量值",
                        "pass", _fmt(item.measured), _fmt(item.permitted),
                        f"差额 {diff:+.2f}㎡ ({pct:.1f}%)，在允许范围内",
                        f"建筑面积汇总表 {b.name}", b.summary_page,
                        calc_process=calc_str))

    return results


def check_special(report):
    results = []

    if report.planning:
        p = report.planning
        if p.real_estate_total_area is not None and p.total_area_measure is not None:
            diff = p.real_estate_total_area - p.total_area_measure
            total_finishing = Decimal("0")
            finishing_details = []
            for b in report.buildings:
                if b.total_area.finishing is not None:
                    total_finishing += b.total_area.finishing
                    finishing_details.append(f"{b.name}={_fmt(b.total_area.finishing)}")

            if total_finishing > 0:
                calc_str = (f"不动产总面积({_fmt(p.real_estate_total_area)})"
                           f" - 规划总面积({_fmt(p.total_area_measure)})"
                           f" = 差异({_fmt(diff)})")
                calc_str += f"\n各栋饰面: {', '.join(finishing_details)} = 合计({_fmt(total_finishing)})"

                if _approx_eq(abs(diff), total_finishing, tol=Decimal("1")):
                    results.append(CheckResult(
                        "特殊检查", "不动产总面积 vs 规划总面积差异=饰面合计",
                        "warning", f"差异{_fmt(diff)}≈饰面{_fmt(total_finishing)}",
                        "口径差异(含/不含饰面)",
                        "不动产含饰面, 规划不含饰面, 差异属正常但报告未注明",
                        page_num=p.indicator_page, calc_process=calc_str))

    facilities = {}
    for b in report.buildings:
        if b.facility.measured is not None and b.facility.measured > 0:
            facilities[b.name] = b.facility.measured

    if len(facilities) >= 2:
        for b in report.buildings:
            sub_measured = b.subitem_sum_measured()
            if sub_measured is not None and b.total_area.measured is not None:
                diff = sub_measured - b.total_area.measured
                if abs(diff) > TOL:
                    matched_facility = None
                    for fname, fval in facilities.items():
                        if fname != b.name and _approx_eq(abs(diff), fval):
                            matched_facility = fname
                            break
                    if matched_facility:
                        parts = []
                        if b.main_function.measured is not None:
                            parts.append(f"主要功能({_fmt(b.main_function.measured)})")
                        if b.roof_stair.measured is not None:
                            parts.append(f"屋面({_fmt(b.roof_stair.measured)})")
                        if b.facility.measured is not None:
                            parts.append(f"配套({_fmt(b.facility.measured)})")
                        calc_str = " + ".join(parts) + f" = {_fmt(sub_measured)}"
                        calc_str += f" ≠ 总面积({_fmt(b.total_area.measured)})"
                        calc_str += f"\n差额 {diff:+.2f}㎡ ≈ {matched_facility}配套设施({_fmt(facilities[matched_facility])}㎡)"

                        results.append(CheckResult(
                            "特殊检查", f"{b.name} 配套设施面积疑似归属错误",
                            "fail", _fmt(sub_measured), _fmt(b.total_area.measured),
                            f"分项合计({sub_measured:.2f})与总面积({b.total_area.measured:.2f})差额{diff:+.2f}㎡"
                            f"≈{matched_facility}配套设施({facilities[matched_facility]:.2f}㎡)"
                            f"，疑似{b.name}配套设施被错误计入{matched_facility}",
                            "建筑面积汇总表", b.summary_page, calc_process=calc_str))

    return results


def generate_data_summary(report):
    """生成提取数据摘要，供GUI展示"""
    lines = []
    lines.append("=" * 60)
    lines.append("一、建筑面积汇总表（提取数据）")
    lines.append("=" * 60)
    for b in report.buildings:
        lines.append(f"\n【{b.name}】 (PDF第{b.summary_page + 1}页)")
        lines.append(f"  基底面积: 许可={_fmt(b.base_area.permitted)}, 测量={_fmt(b.base_area.measured)}")
        lines.append(f"  总建筑面积: 许可={_fmt(b.total_area.permitted)}, 测量={_fmt(b.total_area.measured)}, 饰面={_fmt(b.total_area.finishing)}")
        lines.append(f"  计容面积: 许可={_fmt(b.far_area.permitted)}, 测量={_fmt(b.far_area.measured)}")
        lines.append(f"  主要功能: 许可={_fmt(b.main_function.permitted)}, 测量={_fmt(b.main_function.measured)}")
        lines.append(f"  屋面梯屋: 许可={_fmt(b.roof_stair.permitted)}, 测量={_fmt(b.roof_stair.measured)}")
        lines.append(f"  配套设施: 许可={_fmt(b.facility.permitted)}, 测量={_fmt(b.facility.measured)}")
        lines.append(f"  地下室: 许可={_fmt(b.basement.permitted)}, 测量={_fmt(b.basement.measured)}")
        sub = b.subitem_sum_measured()
        if sub is not None:
            lines.append(f"  → 分项合计(测量) = {_fmt(sub)}")

    lines.append("\n" + "=" * 60)
    lines.append("二、分层面积表（提取数据）")
    lines.append("=" * 60)
    for ft in report.floor_tables:
        lines.append(f"\n【{ft.building_name}】 汇总表(PDF第{ft.summary_page + 1}页) 明细表(PDF第{ft.detail_page + 1}页)")
        lines.append(f"  总车间面积: {_fmt(ft.total_workshop)}")
        lines.append(f"  总套内面积: {_fmt(ft.total_inner)}")
        lines.append(f"  总分摊公建: {_fmt(ft.total_shared_public)}")
        lines.append(f"  总不分摊公建: {_fmt(ft.total_unshared_public)}")
        lines.append(f"  总建筑面积: {_fmt(ft.total_building)}")
        if ft.floors:
            lines.append(f"  逐层数据:")
            for f in sorted(ft.floors, key=lambda x: x.floor_name):
                lines.append(f"    {f.floor_name}: 公建={_fmt(f.public_area)}, 车间={_fmt(f.workshop_area)}, 不分摊公建={_fmt(f.unshared_public_area)}")
            ws = ft.floor_workshop_sum()
            pub = ft.floor_public_sum()
            if ws is not None:
                lines.append(f"  → 逐层车间合计 = {_fmt(ws)}")
            if pub is not None:
                lines.append(f"  → 逐层公建合计 = {_fmt(pub)}")

    lines.append("\n" + "=" * 60)
    lines.append("三、分摊说明（提取数据）")
    lines.append("=" * 60)
    for ap in report.apportionments:
        lines.append(f"\n【{ap.building_name}】 (PDF第{ap.page + 1}页)")
        lines.append(f"  分摊系数: {ap.coefficient:.10f}" if ap.coefficient else "  分摊系数: 缺失")
        lines.append(f"  总套内: {_fmt(ap.total_inner)}")
        lines.append(f"  总分摊: {_fmt(ap.total_shared)}")
        lines.append(f"  总建筑: {_fmt(ap.total_building)}")
        if ap.summary_inner is not None:
            lines.append(f"  汇总行: 套内={_fmt(ap.summary_inner)}, 分摊={_fmt(ap.summary_shared)}, 建筑={_fmt(ap.summary_building)}")
        if ap.sources:
            lines.append(f"  分摊来源({len(ap.sources)}项):")
            for s in ap.sources:
                lines.append(f"    {s.name}: {_fmt(s.area)}")
            ss = ap.source_sum()
            if ss is not None:
                lines.append(f"  → 来源合计 = {_fmt(ss)}")

    lines.append("\n" + "=" * 60)
    lines.append("四、规划指标（提取数据）")
    lines.append("=" * 60)
    if report.planning:
        p = report.planning
        lines.append(f"  指标页: PDF第{p.indicator_page + 1}页")
        lines.append(f"  建筑基底面积: 许可={_fmt(p.base_area_permit)}, 测量={_fmt(p.base_area_measure)}")
        lines.append(f"  总建筑面积: 许可={_fmt(p.total_area_permit)}, 测量={_fmt(p.total_area_measure)}")
        lines.append(f"  总计容面积: 许可={_fmt(p.total_FAR_area_permit)}, 测量={_fmt(p.total_FAR_area_measure)}")
        lines.append(f"  绿化面积: 许可={_fmt(p.green_area_permit)}, 测量={_fmt(p.green_area_measure)}")
        lines.append(f"  不动产总面积: {_fmt(p.real_estate_total_area)}")
    else:
        lines.append("  未提取到规划指标数据")

    return "\n".join(lines)


def run_all_checks(report):
    results = []
    results.extend(check_vertical(report))
    results.extend(check_horizontal(report))
    results.extend(check_apportionment(report))
    results.extend(check_permitted_vs_measured(report))
    results.extend(check_special(report))

    if not results:
        results.append(CheckResult(
            "系统", "未检测到可检查的数据",
            "warning", "", "",
            "可能是PDF格式不匹配或解析失败，请检查PDF是否为标准格式报告"))

    return results


# ==================== EDB对比检查 ====================

def _find_building_by_name(report, name):
    for b in report.buildings:
        if b.name == name:
            return b
    for b in report.buildings:
        if name in b.name or b.name in name:
            return b
    return None


def check_edb_vs_pdf(pdf_report, edb_report):
    results = []

    edb_names = {b.name for b in edb_report.buildings}
    pdf_names = {b.name for b in pdf_report.buildings}

    for name in sorted(edb_names - pdf_names):
        results.append(CheckResult(
            "EDB对比-完整性", f"EDB建筑「{name}」在PDF中未找到",
            "fail", "应在PDF中存在", "未找到",
            f"EDB中有此建筑但PDF解析未识别到，可能是建筑名称不匹配或PDF遗漏",
            "建筑面积汇总表", -1))

    for name in sorted(pdf_names - edb_names):
        results.append(CheckResult(
            "EDB对比-完整性", f"PDF建筑「{name}」在EDB中不存在",
            "warning", "应与EDB一致", "EDB中无此建筑",
            f"PDF中有此建筑但EDB中没有，可能是PDF解析错误识别了不存在的建筑",
            "建筑面积汇总表", -1))

    for edb_b in edb_report.buildings:
        pdf_b = _find_building_by_name(pdf_report, edb_b.name)
        if not pdf_b:
            continue

        checks = [
            ("基底面积", edb_b.base_area, pdf_b.base_area),
            ("总建筑面积", edb_b.total_area, pdf_b.total_area),
            ("计容面积", edb_b.far_area, pdf_b.far_area),
            ("主要功能", edb_b.main_function, pdf_b.main_function),
            ("屋面梯屋", edb_b.roof_stair, pdf_b.roof_stair),
            ("配套设施", edb_b.facility, pdf_b.facility),
            ("地下室", edb_b.basement, pdf_b.basement),
        ]

        for item_name, edb_item, pdf_item in checks:
            for val_type, edb_val, pdf_val in [
                ("许可", edb_item.permitted, pdf_item.permitted),
                ("测量", edb_item.measured, pdf_item.measured),
                ("饰面", edb_item.finishing, pdf_item.finishing),
            ]:
                if edb_val is not None and pdf_val is not None:
                    if not _approx_eq(edb_val, pdf_val):
                        diff = pdf_val - edb_val
                        calc_str = (
                            f"EDB {val_type}={_fmt(edb_val)} vs "
                            f"PDF {val_type}={_fmt(pdf_val)} → 差额{diff:+.2f}㎡"
                        )
                        results.append(CheckResult(
                            "EDB对比-数值", f"{edb_b.name} {item_name}({val_type}) PDF≠EDB",
                            "fail", _fmt(edb_val), _fmt(pdf_val),
                            f"PDF值与EDB源数据不一致，差额{diff:+.2f}㎡",
                            f"建筑面积汇总表 {edb_b.name}", pdf_b.summary_page,
                            calc_process=calc_str))
                elif edb_val is not None and pdf_val is None:
                    if edb_val == 0:
                        continue
                    results.append(CheckResult(
                        "EDB对比-缺失", f"{edb_b.name} {item_name}({val_type}) PDF缺失",
                        "warning", _fmt(edb_val), "缺失",
                        f"EDB中有此值但PDF未提取到",
                        f"建筑面积汇总表 {edb_b.name}", pdf_b.summary_page))

    if edb_report.planning and pdf_report.planning:
        ep = edb_report.planning
        pp = pdf_report.planning
        pi_checks = [
            ("基底面积(许可)", ep.base_area_permit, pp.base_area_permit),
            ("基底面积(测量)", ep.base_area_measure, pp.base_area_measure),
            ("总面积(许可)", ep.total_area_permit, pp.total_area_permit),
            ("总面积(测量)", ep.total_area_measure, pp.total_area_measure),
            ("计容面积(许可)", ep.total_FAR_area_permit, pp.total_FAR_area_permit),
            ("计容面积(测量)", ep.total_FAR_area_measure, pp.total_FAR_area_measure),
        ]
        for name, edb_val, pdf_val in pi_checks:
            if edb_val is not None and pdf_val is not None:
                if not _approx_eq(edb_val, pdf_val):
                    diff = pdf_val - edb_val
                    results.append(CheckResult(
                        "EDB对比-规划指标", f"规划指标 {name} PDF≠EDB",
                        "fail", _fmt(edb_val), _fmt(pdf_val),
                        f"PDF值与EDB源数据不一致，差额{diff:+.2f}㎡",
                        "规划条件核实指标", pp.indicator_page,
                        calc_process=f"EDB={_fmt(edb_val)} vs PDF={_fmt(pdf_val)} → 差额{diff:+.2f}㎡"))

    for edb_ft in edb_report.floor_tables:
        pdf_ft = next(
            (ft for ft in pdf_report.floor_tables
             if ft.building_name == edb_ft.building_name),
            None
        )
        edb_floor_count = len(edb_ft.floors)
        if pdf_ft:
            pdf_floor_count = len(pdf_ft.floors)
            if edb_floor_count != pdf_floor_count:
                results.append(CheckResult(
                    "EDB对比-分层", f"{edb_ft.building_name} 楼层数 PDF({pdf_floor_count})≠EDB({edb_floor_count})",
                    "warning", f"{edb_floor_count}层", f"{pdf_floor_count}层",
                    f"EDB有{edb_floor_count}层，PDF提取到{pdf_floor_count}层",
                    f"分层面积表 {edb_ft.building_name}", pdf_ft.detail_page))
        else:
            results.append(CheckResult(
                "EDB对比-分层", f"{edb_ft.building_name} 分层表在PDF中未找到",
                "warning", "应存在", "未找到",
                f"EDB有{edb_floor_count}层数据但PDF未提取到分层表",
                f"分层面积表 {edb_ft.building_name}", -1))

    return results


def check_edb_unit_vs_pdf(pdf_report, edb_report):
    results = []

    for edb_ua in edb_report.edb_unit_areas:
        pdf_ut = next(
            (ut for ut in pdf_report.unit_tables
             if ut.building_name == edb_ua.building_name),
            None
        )
        if not pdf_ut:
            edb_count = edb_ua.total_workshop_count()
            if edb_count > 0:
                edb_total = sum(
                    (w for floor_ws in edb_ua.floor_areas.values() for w in floor_ws),
                    Decimal("0"))
                results.append(CheckResult(
                    "EDB对比-单元面积", f"{edb_ua.building_name} 单元面积表在PDF中未找到",
                    "fail", f"EDB有{edb_count}个车间(合计{_fmt(edb_total)}㎡)", "未找到",
                    f"EDB有{edb_count}个车间面积数据(合计{_fmt(edb_total)}㎡)但PDF未提取到单元面积表",
                    f"单元面积表 {edb_ua.building_name}", -1))
            continue

        edb_grand_total = sum(
            (w for floor_ws in edb_ua.floor_areas.values() for w in floor_ws),
            Decimal("0"))
        edb_floor_count = len(edb_ua.floor_areas)
        edb_unit_count = edb_ua.total_workshop_count()

        if len(pdf_ut.units) == 0:
            if pdf_ut.total_inner is not None and pdf_ut.total_inner > 0:
                if _approx_eq(edb_grand_total, pdf_ut.total_inner, tol=Decimal("1")):
                    floor_details = ", ".join(
                        f"{fn}层={_fmt(sum(ws, Decimal('0')))}({len(ws)}个)"
                        for fn, ws in sorted(edb_ua.floor_areas.items()))
                    results.append(CheckResult(
                        "EDB对比-单元面积", f"{edb_ua.building_name} 单元套内合计=EDB车间合计",
                        "pass", _fmt(edb_grand_total), _fmt(pdf_ut.total_inner),
                        f"PDF套内合计={_fmt(pdf_ut.total_inner)}，EDB车间合计={_fmt(edb_grand_total)}（{edb_floor_count}层{edb_unit_count}个车间）",
                        f"单元面积表 {edb_ua.building_name}", -1,
                        calc_process=f"EDB各层车间: {floor_details}\n合计 = {_fmt(edb_grand_total)}"))
                else:
                    diff = pdf_ut.total_inner - edb_grand_total
                    floor_details = ", ".join(
                        f"{fn}层={_fmt(sum(ws, Decimal('0')))}({len(ws)}个)"
                        for fn, ws in sorted(edb_ua.floor_areas.items()))
                    results.append(CheckResult(
                        "EDB对比-单元面积", f"{edb_ua.building_name} 单元套内合计≠EDB车间合计",
                        "fail", _fmt(edb_grand_total), _fmt(pdf_ut.total_inner),
                        f"PDF套内合计={_fmt(pdf_ut.total_inner)}，EDB车间合计={_fmt(edb_grand_total)}，差额{diff:+.2f}㎡",
                        f"单元面积表 {edb_ua.building_name}", -1,
                        calc_process=f"EDB各层车间: {floor_details}\n合计 = {_fmt(edb_grand_total)} vs PDF = {_fmt(pdf_ut.total_inner)}"))
            else:
                results.append(CheckResult(
                    "EDB对比-单元面积", f"{edb_ua.building_name} PDF单元套内合计为0(EDB有值)",
                    "fail", f"EDB车间合计={_fmt(edb_grand_total)}", "PDF=0或缺失",
                    f"EDB有{edb_unit_count}个车间面积(合计{_fmt(edb_grand_total)}㎡)，但PDF单元面积表套内合计为0或缺失，"
                    f"VBS脚本可能未正确读取面积块数据",
                    f"单元面积表 {edb_ua.building_name}", -1,
                    calc_process=f"EDB({edb_floor_count}层{edb_unit_count}个车间)合计 = {_fmt(edb_grand_total)} → PDF = 0.00"))
            continue

        pdf_units_by_floor = {}
        for u in pdf_ut.units:
            floor_num = _extract_floor_from_unit_name(u.unit_name)
            if floor_num is not None:
                if floor_num not in pdf_units_by_floor:
                    pdf_units_by_floor[floor_num] = []
                pdf_units_by_floor[floor_num].append(u)

        for floor_num in sorted(edb_ua.floor_areas.keys()):
            edb_workshops = edb_ua.floor_areas[floor_num]
            pdf_units = pdf_units_by_floor.get(floor_num, [])

            edb_count = len(edb_workshops)
            pdf_count = len(pdf_units)

            if pdf_count == 0:
                edb_total = sum(edb_workshops, Decimal("0"))
                results.append(CheckResult(
                    "EDB对比-单元面积", f"{edb_ua.building_name} {floor_num}层 PDF缺少单元",
                    "warning", f"EDB有{edb_count}个车间(合计{_fmt(edb_total)}㎡)", "PDF无此层单元",
                    f"EDB有{edb_count}个车间面积但PDF中{floor_num}层无单元数据",
                    f"单元面积表 {edb_ua.building_name}", -1))
                continue

            zero_units = [u for u in pdf_units if u.inner_area is not None and u.inner_area == 0]
            if zero_units:
                edb_total = sum(edb_workshops, Decimal("0"))
                edb_str = ", ".join(_fmt(w) for w in edb_workshops)
                results.append(CheckResult(
                    "EDB对比-单元面积", f"{edb_ua.building_name} {floor_num}层 单元面积为0(EDB有值)",
                    "fail", f"EDB车间面积: {edb_str}", f"PDF: {len(zero_units)}个单元面积为0",
                    f"PDF中{len(zero_units)}/{pdf_count}个单元套内面积为0，但EDB面积块表有{edb_count}个车间面积({_fmt(edb_total)}㎡)，"
                    f"VBS脚本可能未正确读取面积块数据",
                    f"单元面积表 {edb_ua.building_name}", -1,
                    calc_process=f"EDB车间({floor_num}层): {edb_str} → PDF全为0.00"))
                continue

            if pdf_count != edb_count:
                results.append(CheckResult(
                    "EDB对比-单元面积", f"{edb_ua.building_name} {floor_num}层 单元数不匹配",
                    "warning", f"EDB={edb_count}个车间", f"PDF={pdf_count}个单元",
                    f"EDB有{edb_count}个车间面积，PDF有{pdf_count}个单元，可能存在单元重复或遗漏",
                    f"单元面积表 {edb_ua.building_name}", -1))
                continue

            matched = True
            mismatch_details = []
            for edb_w, pdf_u in zip(sorted(edb_workshops), pdf_units):
                if pdf_u.inner_area is not None and not _approx_eq(edb_w, pdf_u.inner_area, tol=Decimal("1")):
                    matched = False
                    diff = pdf_u.inner_area - edb_w
                    mismatch_details.append(
                        f"{pdf_u.unit_name}: PDF={_fmt(pdf_u.inner_area)} vs EDB={_fmt(edb_w)}(差{diff:+.2f})")

            if matched:
                edb_str = ", ".join(_fmt(w) for w in edb_workshops)
                results.append(CheckResult(
                    "EDB对比-单元面积", f"{edb_ua.building_name} {floor_num}层 单元面积=EDB车间面积",
                    "pass", edb_str, edb_str,
                    f"PDF {pdf_count}个单元面积与EDB面积块一致",
                    f"单元面积表 {edb_ua.building_name}", -1))
            else:
                results.append(CheckResult(
                    "EDB对比-单元面积", f"{edb_ua.building_name} {floor_num}层 单元面积≠EDB车间面积",
                    "warning", "应与EDB一致", "存在差异",
                    "; ".join(mismatch_details),
                    f"单元面积表 {edb_ua.building_name}", -1))

    return results


def _extract_floor_from_unit_name(name):
    """从单元名称中提取楼层号，如 '厂房四101室' -> 1, '厂房三202室' -> 2"""
    import re
    m = re.search(r'(\d{3,4})', name)
    if m:
        room_str = m.group(1)
        if len(room_str) == 3:
            return int(room_str[0])
        elif len(room_str) == 4:
            return int(room_str[:2])
    return None


def check_edb_internal(edb_report):
    results = []

    for b in edb_report.buildings:
        sub_measured = b.subitem_sum_measured()
        if sub_measured is not None and b.total_area.measured is not None:
            if not _approx_eq(sub_measured, b.total_area.measured):
                diff = sub_measured - b.total_area.measured
                parts = []
                if b.main_function.measured is not None:
                    parts.append(f"主要功能({_fmt(b.main_function.measured)})")
                if b.roof_stair.measured is not None:
                    parts.append(f"屋面({_fmt(b.roof_stair.measured)})")
                if b.facility.measured is not None:
                    parts.append(f"配套({_fmt(b.facility.measured)})")
                if b.basement.measured is not None:
                    parts.append(f"地下室({_fmt(b.basement.measured)})")
                calc_str = " + ".join(parts) + f" = {_fmt(sub_measured)}"
                calc_str += f" ≠ 总面积({_fmt(b.total_area.measured)})"
                results.append(CheckResult(
                    "EDB内部一致性", f"{b.name} EDB分项合计(测量)≠总面积(测量)",
                    "fail", _fmt(b.total_area.measured), _fmt(sub_measured),
                    f"EDB数据库内部不一致，差额{diff:+.2f}㎡，VBS原样输出至PDF",
                    "EDB数据库", -1, calc_process=calc_str))

        sub_permitted = b.subitem_sum_permitted()
        if sub_permitted is not None and b.total_area.permitted is not None:
            if not _approx_eq(sub_permitted, b.total_area.permitted):
                diff = sub_permitted - b.total_area.permitted
                results.append(CheckResult(
                    "EDB内部一致性", f"{b.name} EDB分项合计(许可)≠总面积(许可)",
                    "fail", _fmt(b.total_area.permitted), _fmt(sub_permitted),
                    f"EDB数据库内部不一致，差额{diff:+.2f}㎡，VBS原样输出至PDF",
                    "EDB数据库", -1))

    building_total = Decimal("0")
    building_far = Decimal("0")
    for b in edb_report.buildings:
        if b.total_area.measured is not None:
            building_total += b.total_area.measured
        if b.far_area.measured is not None:
            building_far += b.far_area.measured

    p = edb_report.planning
    if p and p.total_area_measure is not None and building_total > 0:
        if not _approx_eq(building_total, p.total_area_measure, tol=Decimal("1")):
            diff = building_total - p.total_area_measure
            results.append(CheckResult(
                "EDB内部一致性", "EDB各栋总面积合计≠规划指标总面积",
                "fail", _fmt(p.total_area_measure), _fmt(building_total),
                f"各栋合计({_fmt(building_total)}) ≠ 规划指标({_fmt(p.total_area_measure)})，差额{diff:+.2f}㎡",
                "EDB数据库", -1))

    if p and p.total_FAR_area_measure is not None and building_far > 0:
        if not _approx_eq(building_far, p.total_FAR_area_measure, tol=Decimal("1")):
            diff = building_far - p.total_FAR_area_measure
            results.append(CheckResult(
                "EDB内部一致性", "EDB各栋计容合计≠规划指标总计容",
                "fail", _fmt(p.total_FAR_area_measure), _fmt(building_far),
                f"各栋计容合计({_fmt(building_far)}) ≠ 规划指标({_fmt(p.total_FAR_area_measure)})，差额{diff:+.2f}㎡",
                "EDB数据库", -1))

    return results


def generate_edb_summary(edb_report):
    lines = []
    lines.append("=" * 60)
    lines.append("EDB数据库提取数据（Ground Truth）")
    lines.append("=" * 60)
    lines.append(f"\n建筑数量: {len(edb_report.buildings)}")
    lines.append(f"分层表数量: {len(edb_report.floor_tables)}")

    for b in edb_report.buildings:
        lines.append(f"\n【{b.name}】")
        lines.append(f"  基底面积: 许可={_fmt(b.base_area.permitted)}, 测量={_fmt(b.base_area.measured)}")
        lines.append(f"  总建筑面积: 许可={_fmt(b.total_area.permitted)}, 测量={_fmt(b.total_area.measured)}, 饰面={_fmt(b.total_area.finishing)}")
        lines.append(f"  计容面积: 许可={_fmt(b.far_area.permitted)}, 测量={_fmt(b.far_area.measured)}")
        lines.append(f"  主要功能: 许可={_fmt(b.main_function.permitted)}, 测量={_fmt(b.main_function.measured)}")
        lines.append(f"  屋面梯屋: 许可={_fmt(b.roof_stair.permitted)}, 测量={_fmt(b.roof_stair.measured)}")
        lines.append(f"  配套设施: 许可={_fmt(b.facility.permitted)}, 测量={_fmt(b.facility.measured)}")
        lines.append(f"  地下室: 许可={_fmt(b.basement.permitted)}, 测量={_fmt(b.basement.measured)}")
        sub = b.subitem_sum_measured()
        if sub is not None:
            lines.append(f"  → 分项合计(测量) = {_fmt(sub)}")

    if edb_report.planning:
        p = edb_report.planning
        lines.append(f"\n【规划指标】")
        lines.append(f"  基底面积: 许可={_fmt(p.base_area_permit)}, 测量={_fmt(p.base_area_measure)}")
        lines.append(f"  总建筑面积: 许可={_fmt(p.total_area_permit)}, 测量={_fmt(p.total_area_measure)}")
        lines.append(f"  总计容面积: 许可={_fmt(p.total_FAR_area_permit)}, 测量={_fmt(p.total_FAR_area_measure)}")
        lines.append(f"  绿化面积: 许可={_fmt(p.green_area_permit)}, 测量={_fmt(p.green_area_measure)}")

    for ft in edb_report.floor_tables:
        lines.append(f"\n【{ft.building_name} 分层表】 ({len(ft.floors)}层)")
        lines.append(f"  总套内: {_fmt(ft.total_inner)}, 总公建: {_fmt(ft.total_public)}, 总建筑: {_fmt(ft.total_building)}")

    return "\n".join(lines)


def run_all_checks_with_edb(pdf_report, edb_report):
    results = []
    results.extend(check_vertical(pdf_report))
    results.extend(check_horizontal(pdf_report))
    results.extend(check_apportionment(pdf_report))
    results.extend(check_permitted_vs_measured(pdf_report))
    results.extend(check_special(pdf_report))
    results.extend(check_edb_internal(edb_report))
    results.extend(check_edb_vs_pdf(pdf_report, edb_report))
    results.extend(check_edb_unit_vs_pdf(pdf_report, edb_report))

    if not results:
        results.append(CheckResult(
            "系统", "未检测到可检查的数据",
            "warning", "", "",
            "可能是PDF格式不匹配或解析失败，请检查PDF是否为标准格式报告"))

    return results
