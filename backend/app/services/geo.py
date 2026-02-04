from __future__ import annotations

from sqlalchemy import Float, func
from sqlalchemy.sql.elements import ColumnElement


def haversine_distance_m(*, lat_col, lng_col, lat: float, lng: float) -> ColumnElement[float]:
    """
    SQL 版 Haversine（米），无需 PostGIS。
    参考：地球半径 6371000m。
    """
    lat1 = func.radians(lat_col)
    lng1 = func.radians(lng_col)
    lat2 = func.radians(lat)
    lng2 = func.radians(lng)

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = func.pow(func.sin(dlat / 2.0), 2) + func.cos(lat1) * func.cos(lat2) * func.pow(func.sin(dlng / 2.0), 2)
    c = 2.0 * func.asin(func.sqrt(a))
    return (6371000.0 * c).cast(Float)

