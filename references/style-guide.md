# style-guide.md（兼容别名）

本 skill 的文体 / 事实规范**只有一份真源**：[report-guide.md](report-guide.md)。

之所以不沿用 `style-guide` 这个正名：周报不讲究「文风」，这份文档是**事实契约与可机检规范**，
旧名字会诱导模型去做润色、加梗、造词——而那正是要禁止的。这里只保留一个别名入口，
方便按原 `goushi-writing` 的目录习惯找到它。

**不要在两份文件里各写一套规则。** 任何新增条款都写进 `report-guide.md`，
并同步 `scripts/lint.py` 的可机检规则、`assets/views.json` 的配额，
以及图表 / PDF 产物对应的 `scripts/make_figs.py`、`scripts/build_pdf.py` 落点（见 §4.5）。
