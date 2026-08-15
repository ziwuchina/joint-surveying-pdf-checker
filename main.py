import sys
import os
import re
import pymupdf as fitz
from decimal import Decimal

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QTextEdit, QProgressBar, QStatusBar, QHeaderView,
    QSplitter, QMessageBox, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from pdf_parser import parse_pdf
from checker import (
    run_all_checks, run_all_checks_with_edb,
    generate_data_summary, generate_edb_summary,
)
from models import CheckResult


class ParseWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, pdf_path, edb_path=None):
        super().__init__()
        self.pdf_path = pdf_path
        self.edb_path = edb_path

    def run(self):
        try:
            self.progress.emit("正在解析PDF...")
            report = parse_pdf(self.pdf_path)
            self.progress.emit(
                f"PDF解析完成: {len(report.buildings)}栋建筑, "
                f"{len(report.floor_tables)}个分层表, "
                f"{len(report.unit_tables)}个单元表, "
                f"{len(report.apportionments)}个分摊说明"
            )

            edb_report = None
            edb_summary = ""
            if self.edb_path:
                self.progress.emit("正在读取EDB数据库...")
                try:
                    from edb_reader import EDBReader
                    reader = EDBReader(self.edb_path)
                    edb_report = reader.read_all()
                    edb_summary = generate_edb_summary(edb_report)
                    self.progress.emit(
                        f"EDB读取完成: {len(edb_report.buildings)}栋建筑, "
                        f"{len(edb_report.floor_tables)}个分层表"
                    )
                except Exception as e:
                    self.progress.emit(f"EDB读取失败: {e}，将仅使用PDF检查")

            self.progress.emit("正在执行检查...")
            if edb_report:
                results = run_all_checks_with_edb(report, edb_report)
            else:
                results = run_all_checks(report)

            data_summary = generate_data_summary(report)
            self.finished.emit((report, results, data_summary, edb_report, edb_summary))
        except Exception as e:
            self.error.emit(str(e))


class PDFCheckerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.report = None
        self.edb_report = None
        self.results = []
        self.data_summary = ""
        self.edb_summary = ""
        self.pdf_path = ""
        self.edb_path = ""
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("联合测绘PDF报告检查系统")
        self.setMinimumSize(1200, 750)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- 顶部工具栏 ---
        top_bar = QHBoxLayout()
        self.btn_open = QPushButton("  打开PDF报告")
        self.btn_open.setFixedHeight(34)
        self.btn_open.setStyleSheet(
            "QPushButton { background-color: #4B3FE3; color: white; "
            "border-radius: 5px; font-size: 14px; padding: 0 24px; } "
            "QPushButton:hover { background-color: #3C2ECA; }"
        )
        self.btn_open.clicked.connect(self.open_pdf)

        self.btn_edb = QPushButton("  关联EDB数据库")
        self.btn_edb.setFixedHeight(34)
        self.btn_edb.setStyleSheet(
            "QPushButton { border: 1.5px solid #2BB673; color: #2BB673; "
            "border-radius: 5px; font-size: 14px; padding: 0 20px; } "
            "QPushButton:hover { background-color: #F0FBF5; } "
            "QPushButton:disabled { color: #999; border-color: #ccc; }"
        )
        self.btn_edb.clicked.connect(self.select_edb)

        self.btn_annotate = QPushButton("  生成标注版PDF")
        self.btn_annotate.setFixedHeight(34)
        self.btn_annotate.setEnabled(False)
        self.btn_annotate.setStyleSheet(
            "QPushButton { border: 1.5px solid #4B3FE3; color: #4B3FE3; "
            "border-radius: 5px; font-size: 14px; padding: 0 24px; } "
            "QPushButton:hover { background-color: #F2F7FF; } "
            "QPushButton:disabled { color: #999; border-color: #ccc; }"
        )
        self.btn_annotate.clicked.connect(self.generate_annotated_pdf)

        self.lbl_file = QLabel("未选择文件")
        self.lbl_file.setStyleSheet("color: #666; font-size: 13px;")

        top_bar.addWidget(self.btn_open)
        top_bar.addWidget(self.btn_edb)
        top_bar.addWidget(self.btn_annotate)
        top_bar.addWidget(self.lbl_file, 1)
        layout.addLayout(top_bar)

        # --- 进度条 ---
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        # --- 统计栏 ---
        stats_bar = QHBoxLayout()
        self.lbl_stats = QLabel("等待检查...")
        self.lbl_stats.setStyleSheet("font-size: 13px; color: #52525B; padding: 4px 0;")
        stats_bar.addWidget(self.lbl_stats)
        stats_bar.addStretch()
        layout.addLayout(stats_bar)

        # --- 主区域 ---
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：检查结果树
        tree_group = QGroupBox("检查结果")
        tree_layout = QVBoxLayout(tree_group)
        tree_layout.setContentsMargins(4, 4, 4, 4)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["检查项", "状态", "期望值", "实际值"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemClicked.connect(self.on_item_clicked)
        tree_layout.addWidget(self.tree)

        # 右侧：标签页（检查详情 + 提取数据 + EDB数据）
        right_group = QGroupBox("详情")
        right_layout = QVBoxLayout(right_group)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.tab_widget = QTabWidget()

        # Tab 1: 检查详情
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(
            "font-size: 13px; font-family: 'Consolas', 'Microsoft YaHei', monospace;"
        )
        self.tab_widget.addTab(self.detail_text, "检查详情")

        # Tab 2: 提取数据汇总
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        self.data_text.setStyleSheet(
            "font-size: 12px; font-family: 'Consolas', 'Microsoft YaHei', monospace;"
        )
        self.tab_widget.addTab(self.data_text, "PDF提取数据")

        # Tab 3: EDB数据
        self.edb_text = QTextEdit()
        self.edb_text.setReadOnly(True)
        self.edb_text.setStyleSheet(
            "font-size: 12px; font-family: 'Consolas', 'Microsoft YaHei', monospace;"
        )
        self.tab_widget.addTab(self.edb_text, "EDB数据库")
        self.tab_widget.setTabEnabled(2, False)

        right_layout.addWidget(self.tab_widget)

        splitter.addWidget(tree_group)
        splitter.addWidget(right_group)
        splitter.setSizes([550, 650])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, 1)
        self.statusBar().showMessage("就绪")

    # ========== EDB文件选择 ==========
    def select_edb(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择EDB数据库", "", "EDB数据库 (*.edb)"
        )
        if not path:
            return

        self.edb_path = path
        edb_name = os.path.basename(path)
        self.lbl_file.setText(
            f"PDF: {os.path.basename(self.pdf_path) if self.pdf_path else '未选择'}"
            f"  |  EDB: {edb_name}"
        )
        self.statusBar().showMessage(f"已关联EDB: {edb_name}")

    # ========== 文件打开 ==========
    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF报告", "", "PDF文件 (*.pdf)"
        )
        if not path:
            return

        self.pdf_path = path
        edb_name = os.path.basename(self.edb_path) if self.edb_path else "未关联"
        self.lbl_file.setText(
            f"PDF: {os.path.basename(path)}  |  EDB: {edb_name}"
        )
        self.btn_open.setEnabled(False)
        self.btn_edb.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.statusBar().showMessage("正在解析...")

        self.worker = ParseWorker(path, self.edb_path if self.edb_path else None)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, msg):
        self.statusBar().showMessage(msg)

    def on_finished(self, data):
        self.report, self.results, self.data_summary, self.edb_report, self.edb_summary = data
        self.progress.setVisible(False)
        self.btn_open.setEnabled(True)
        self.btn_edb.setEnabled(True)
        self.btn_annotate.setEnabled(True)

        self.populate_tree()
        self.data_text.setPlainText(self.data_summary)

        if self.edb_report:
            self.edb_text.setPlainText(self.edb_summary)
            self.tab_widget.setTabEnabled(2, True)
        else:
            self.edb_text.setPlainText("")
            self.tab_widget.setTabEnabled(2, False)

        self.statusBar().showMessage(f"检查完成: {len(self.results)}项")

        fails = sum(1 for r in self.results if r.status == 'fail')
        warnings = sum(1 for r in self.results if r.status == 'warning')
        passes = sum(1 for r in self.results if r.status == 'pass')

        self.lbl_stats.setText(
            f"  <span style='color:#1DC981;font-weight:bold'>✓ 通过 {passes}</span>"
            f"  <span style='color:#E8463A;font-weight:bold'>✗ 错误 {fails}</span>"
            f"  <span style='color:#EFAA17;font-weight:bold'>⚠ 警告 {warnings}</span>"
            f"  <span style='color:#888'>共 {len(self.results)} 项</span>"
            + (f"  <span style='color:#2BB673'>● EDB已关联</span>" if self.edb_report else "")
        )

        if fails > 0:
            QMessageBox.warning(
                self, "检查完成",
                f"发现 {fails} 项错误！\n请查看检查结果详情。\n"
                f"可点击「生成标注版PDF」在原报告上标注错误。"
            )
        elif warnings > 0:
            QMessageBox.information(
                self, "检查完成",
                f"未发现错误，但有 {warnings} 项警告需关注。"
            )
        else:
            QMessageBox.information(self, "检查完成", "所有检查项均通过！")

    def on_error(self, msg):
        self.progress.setVisible(False)
        self.btn_open.setEnabled(True)
        self.btn_edb.setEnabled(True)
        self.statusBar().showMessage("解析失败")
        QMessageBox.critical(self, "错误", f"PDF解析失败:\n{msg}")

    # ========== 结果树填充 ==========
    def populate_tree(self):
        self.tree.clear()

        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = []
            categories[r.category].append(r)

        status_colors = {
            'pass': QColor(29, 201, 129),
            'fail': QColor(232, 70, 58),
            'warning': QColor(239, 170, 23),
            'skip': QColor(150, 150, 150),
        }
        status_text = {
            'pass': '✓ 通过',
            'fail': '✗ 错误',
            'warning': '⚠ 警告',
            'skip': '— 跳过',
        }

        for cat_name, items in sorted(categories.items()):
            cat_item = QTreeWidgetItem([cat_name, "", "", ""])
            cat_font = cat_item.font(0)
            cat_font.setBold(True)
            cat_item.setFont(0, cat_font)

            cat_fails = sum(1 for r in items if r.status == 'fail')
            cat_warns = sum(1 for r in items if r.status == 'warning')
            if cat_fails > 0:
                cat_item.setBackground(0, QColor(255, 240, 240))
            elif cat_warns > 0:
                cat_item.setBackground(0, QColor(255, 250, 230))
            else:
                cat_item.setBackground(0, QColor(240, 255, 244))

            for r in items:
                child = QTreeWidgetItem([
                    r.check_name,
                    status_text.get(r.status, r.status),
                    r.expected,
                    r.actual,
                ])
                color = status_colors.get(r.status, QColor(150, 150, 150))
                child.setForeground(1, color)

                if r.status == 'fail':
                    child.setBackground(0, QColor(255, 245, 245))
                elif r.status == 'warning':
                    child.setBackground(0, QColor(255, 252, 240))

                child.setData(0, Qt.UserRole, r)
                cat_item.addChild(child)

            cat_item.setText(1, f"{len(items)}项")
            self.tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)

    def on_item_clicked(self, item, column):
        r = item.data(0, Qt.UserRole)
        if r is None:
            return

        status_color = (
            '#E8463A' if r.status == 'fail'
            else '#EFAA17' if r.status == 'warning'
            else '#1DC981'
        )
        page_info = ""
        if r.page_num >= 0:
            page_info = f"<tr><td style='padding:4px 8px;color:#666;'>PDF页码</td><td style='padding:4px 8px;'>第 {r.page_num + 1} 页 (索引{r.page_num})</td></tr>"
        if r.page_hint:
            page_info += f"<tr><td style='padding:4px 8px;color:#666;'>位置提示</td><td style='padding:4px 8px;'>{r.page_hint}</td></tr>"

        calc_process_html = ""
        if r.calc_process:
            process_escaped = r.calc_process.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
            calc_process_html = f"""
            <hr style="border:none;border-top:1px solid #ddd;margin:8px 0;">
            <p style="padding:4px 8px;"><b>计算过程:</b></p>
            <div style="padding:8px 12px;background:#f5f5f5;border-radius:4px;font-family:monospace;font-size:12px;white-space:pre-wrap;">{process_escaped}</div>
            """

        html = f"""
        <html><body style="font-family:'Microsoft YaHei',sans-serif;font-size:13px;">
        <h3 style="color:{status_color};">{r.check_name}</h3>
        <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:4px 8px;color:#666;width:80px;">类别</td><td style="padding:4px 8px;">{r.category}</td></tr>
        <tr><td style="padding:4px 8px;color:#666;">状态</td><td style="padding:4px 8px;font-weight:bold;color:{status_color};">{r.status.upper()}</td></tr>
        <tr><td style="padding:4px 8px;color:#666;">期望值</td><td style="padding:4px 8px;font-family:monospace;">{r.expected}</td></tr>
        <tr><td style="padding:4px 8px;color:#666;">实际值</td><td style="padding:4px 8px;font-family:monospace;">{r.actual}</td></tr>
        {page_info}
        </table>
        <hr style="border:none;border-top:1px solid #ddd;margin:8px 0;">
        <p style="padding:4px 8px;"><b>详情:</b><br>{r.detail}</p>
        {calc_process_html}
        </body></html>
        """
        self.detail_text.setHtml(html)
        self.tab_widget.setCurrentIndex(0)

    # ========== PDF标注生成 ==========
    def generate_annotated_pdf(self):
        if not self.report or not self.pdf_path:
            return

        fails = [r for r in self.results if r.status == 'fail']
        warnings = [r for r in self.results if r.status == 'warning']
        if not fails and not warnings:
            QMessageBox.information(self, "无异常", "未发现错误或警告，无需生成标注版。")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存标注版PDF",
            os.path.splitext(self.pdf_path)[0] + "_检查标注版.pdf",
            "PDF文件 (*.pdf)"
        )
        if not save_path:
            return

        try:
            self.annotate_pdf(save_path)
            QMessageBox.information(
                self, "完成",
                f"标注版PDF已保存:\n{save_path}\n\n"
                f"共标注 {len(fails)} 处错误、{len(warnings)} 处警告。"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成标注PDF失败:\n{str(e)}")

    def annotate_pdf(self, out_path):
        doc = fitz.open(self.pdf_path)
        RED = (0.75, 0.0, 0.0)
        ORANGE = (0.85, 0.45, 0.0)
        RED_FILL = (1, 0.92, 0.92)
        ORANGE_FILL = (1, 0.95, 0.88)
        FONT = r"C:\Windows\Fonts\simhei.ttf"

        page_errors = {}
        error_num = 0
        for r in self.results:
            if r.status not in ('fail', 'warning'):
                continue
            error_num += 1

            page_idx = r.page_num if r.page_num >= 0 else self._find_error_page_fallback(doc, r)
            if page_idx < 0:
                continue

            if page_idx not in page_errors:
                page_errors[page_idx] = []
            page_errors[page_idx].append((error_num, r))

        for page_idx, errs in page_errors.items():
            page = doc[page_idx]
            pw = page.rect.width
            ph = page.rect.height

            box_height = min(20 + len(errs) * 22, 120)
            box = fitz.Rect(25, ph - box_height - 5, pw - 25, ph - 5)

            fill_color = RED_FILL if any(r.status == 'fail' for _, r in errs) else ORANGE_FILL
            border_color = RED if any(r.status == 'fail' for _, r in errs) else ORANGE

            page.draw_rect(box, color=border_color, fill=fill_color, width=1.5)

            y = box.y0 + 5
            for num, r in errs:
                color = RED if r.status == 'fail' else ORANGE
                prefix = f"[错误{num}]" if r.status == 'fail' else f"[警告{num}]"
                text = f"{prefix} {r.check_name}: {r.detail[:80]}"
                if len(r.detail) > 80:
                    text += "..."

                text_rect = fitz.Rect(box.x0 + 5, y, box.x1 - 5, y + 18)
                page.insert_textbox(
                    text_rect, text,
                    fontsize=6.5, color=color, fontname="simhei", fontfile=FONT
                )
                y += 20

        # 末尾汇总页
        all_issues = [(i, r) for i, r in enumerate(
            [r for r in self.results if r.status in ('fail', 'warning')], 1
        )]

        if all_issues:
            summary_page = doc.new_page(width=595, height=842)

            summary_page.insert_text(
                fitz.Point(40, 40),
                "PDF报告检查结果汇总",
                fontsize=16, color=RED, fontname="simhei", fontfile=FONT
            )

            fails_count = sum(1 for _, r in all_issues if r.status == 'fail')
            warns_count = sum(1 for _, r in all_issues if r.status == 'warning')
            edb_tag = " (EDB对比)" if self.edb_report else ""
            summary_page.insert_text(
                fitz.Point(40, 65),
                f"共发现 {fails_count} 项错误，{warns_count} 项警告{edb_tag}",
                fontsize=11, color=(0.3, 0.3, 0.3), fontname="simhei", fontfile=FONT
            )

            y = 90
            for num, r in all_issues:
                if y > 800:
                    summary_page = doc.new_page(width=595, height=842)
                    y = 40

                color = RED if r.status == 'fail' else ORANGE
                prefix = "✗" if r.status == 'fail' else "⚠"

                line1 = f"{prefix} [{r.category}] {r.check_name}"
                summary_page.insert_text(
                    fitz.Point(40, y),
                    line1[:70],
                    fontsize=9, color=color, fontname="simhei", fontfile=FONT
                )

                line2 = f"  期望: {r.expected}  实际: {r.actual}"
                summary_page.insert_text(
                    fitz.Point(50, y + 14),
                    line2[:70],
                    fontsize=8, color=(0.4, 0.4, 0.4), fontname="simhei", fontfile=FONT
                )

                detail_short = r.detail[:65] + ("..." if len(r.detail) > 65 else "")
                summary_page.insert_text(
                    fitz.Point(50, y + 28),
                    detail_short,
                    fontsize=8, color=(0.5, 0.5, 0.5), fontname="simhei", fontfile=FONT
                )

                page_str = f"第{r.page_num + 1}页" if r.page_num >= 0 else "未定位"
                summary_page.insert_text(
                    fitz.Point(400, y + 14),
                    page_str,
                    fontsize=8, color=(0.6, 0.6, 0.6), fontname="simhei", fontfile=FONT
                )

                y += 42

        doc.save(out_path, garbage=4, deflate=True)
        doc.close()

    def _find_error_page_fallback(self, doc, result):
        keywords = []
        for m in re.finditer(r'厂房[一二三四五六七八九十]+|地下室', result.check_name):
            keywords.append(m.group())
        if '配套设施' in result.check_name:
            keywords.append('配套设施')
        if '分摊系数' in result.check_name:
            keywords.append('分摊系数')

        if result.expected and result.expected != "应有值" and result.expected != "应在PDF中存在":
            nums = re.findall(r'\d+\.?\d*', result.expected)
            keywords.extend(nums[:2])

        for kw in keywords:
            for i in range(len(doc)):
                if doc[i].search_for(kw):
                    return i

        return -1


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    window = PDFCheckerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
