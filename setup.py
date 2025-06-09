# setup.py
"""HEMSデータ収集クライアントのパッケージ設定。

このスクリプトは `setuptools` を使用して、プロジェクトのパッケージング、
依存関係の定義、およびエントリポイントの設定を行います。
"""
import os
from setuptools import setup, find_packages

# hems_data_collector/config.py からバージョンを読み込む
def get_version():
    version_filepath = os.path.join(os.path.dirname(__file__), 'hems_data_collector', 'config.py')
    with open(version_filepath) as f:
        for line in f:
            if line.startswith('VERSION'):
                return line.strip().split()[-1].strip('"')
    raise RuntimeError("バージョン文字列が見つかりません。")

# README.md を long_description として読み込む
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name="hems-data-collector",
    version=get_version(),
    author="Hiroki Kato",
    author_email="hiroki.kato@colorfulclover.net",
    description="スマートメーター(HEMS)からデータを収集するツール",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/colorfulclover/cc-hems-data-collector",
    packages=find_packages(),
    install_requires=[
        "pyserial>=3.5",
        "pyyaml>=6.0",
        "python-dotenv>=1.1.0",
        "croniter>=6.0.0",
        "requests>=2.32.0",
    ],
    extras_require={
        "gcloud": ["google-cloud-pubsub>=2.13.0"],
    },
    entry_points={
        "console_scripts": [
            "hems-data-collector=hems_data_collector.main:main",
        ],
    },
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language : Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.11',
)