"""Shared, inspectable benchmark statistics. No inferred/fabricated observations."""
import importlib.metadata
import math
import os
from pathlib import Path
import platform
import statistics
import sys


def stats(values):
    values=list(values)
    if not values:
        return {'count':0,'median_seconds':None,'p95_seconds':None}
    return {'count':len(values),'median_seconds':statistics.median(values),
            'p95_seconds':sorted(values)[math.ceil(.95*len(values))-1]}


def environment():
    import psutil
    cpu=platform.processor()
    if Path('/proc/cpuinfo').exists():
        cpu=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),cpu)
    memory_limit=Path('/sys/fs/cgroup/memory.max')
    return {'python':platform.python_version(),'platform':platform.platform(),'cpu':cpu,
            'logical_cpus':os.cpu_count(),'system_memory_bytes':psutil.virtual_memory().total,
            'container_memory_limit':memory_limit.read_text().strip() if memory_limit.exists() else None,
            'duckdb_memory_limit':'512MB','duckdb_threads':2,
            'packages':{n:importlib.metadata.version(n) for n in ('duckdb','estnltk','estnltk-core','nltk','regex')},
            'p95_method':'nearest rank; with 5 observations p95 equals max',
            'cache_policy':'fresh Python process per case; OS file cache is not cleared'}


def peak_rss_bytes():
    if sys.platform=='win32':
        import psutil
        return psutil.Process().memory_info().peak_wset
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
