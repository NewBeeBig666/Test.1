@echo off
rem 数据渠道自动更新 + 封面补充 + 质量监控（可挂 Windows 计划任务）
rem 计划任务示例（每日 03:00）：
rem   schtasks /Create /SC DAILY /TN RecSysDataUpdate /ST 03:00 /TR "E:\ZcodeSpace\New Demo\update_datasets.bat"

set PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%
set ROOT=%~dp0

echo [1/3] 更新可直连数据渠道（MovieTweetings / Gutenberg）...
cd /d "%ROOT%recommender" && py -3 dataset_channels.py --update

echo [2/3] 电影封面补充（IMDb 海报，断点续传，仅处理缺失项）...
py -3 fetch_covers.py

echo [3/3] 生成数据质量监控报告...
py -3 dataset_channels.py --quality

echo.
echo 完成。报告：%ROOT%recommender\reports_all\data_quality.md
echo 链接有效性另由后端每日 04:30 自动抽查（管理后台可手动触发）。
