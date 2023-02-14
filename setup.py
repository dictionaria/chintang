from setuptools import setup


setup(
    name='cldfbench_chintang',
    py_modules=['cldfbench_chintang'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'cldfbench.dataset': [
            'chintang=cldfbench_chintang:Dataset',
        ]
    },
    install_requires=[
        'cldfbench',
        'pydictionaria',
    ],
    extras_require={
        'test': [
            'pytest-cldf',
        ],
    },
)
