name: JDM RSS Hunter
on:
  schedule:
    - cron: '0 7 * * *'  # 8h CET = 7h UTC
  workflow_dispatch:  # Manuel test
jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: '3.12'}
    - run: pip install -r requirements.txt
    - run: python jdm_hunter.py
    - uses: stefanzweifel/git-auto-commit-action@v5
      with:
        commit_message: 'Update RSS [$(date)]'
        file_pattern: '*.xml'
