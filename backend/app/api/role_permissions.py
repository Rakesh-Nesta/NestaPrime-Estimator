from fastapi import APIRouter, Depends, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel

from app.core.auth import get_current_user, require_roles
from app.models.user import UserRole

router = APIRouter(tags=["role-permissions"])

# Amendment 51 (Section 55): the Director's "who can do what" screen, generated
# from the live route table instead of a hand-kept file. require_roles() tags the
# dependency it returns with the roles it enforces (`allowed_roles`), so every
# gated route reports its own gate: a new or changed gate shows up here with no
# one having to remember to edit anything. Director-only, like user management --
# it describes the system's access rules.
ROLE_ORDER = [role.value for role in UserRole]

# Optional nicer wording for a route whose function name reads awkwardly, keyed by
# the route function's name. Empty by default: the humanised function name is
# used ("create_project" -> "Create project").
LABEL_OVERRIDES: dict[str, str] = {}


class RouteItemOut(BaseModel):
    method: str
    path: str
    label: str


class GroupOut(BaseModel):
    roles: list[str]
    items: list[RouteItemOut]


class AreaOut(BaseModel):
    area: str
    groups: list[GroupOut]


class UngatedRouteOut(RouteItemOut):
    # "any_signed_in": needs a valid login but no particular role (e.g. /auth/me);
    # "public": needs no sign-in at all (e.g. /auth/login, /health).
    access: str


class RolePermissionsOut(BaseModel):
    roles: list[str]
    gated_route_count: int
    areas: list[AreaOut]
    ungated: list[UngatedRouteOut]


def _flatten(routes):
    """The app's effective routes. Newer FastAPI (0.14x) stores each included
    router lazily as an `_IncludedRouter` wrapper, whose `effective_route_contexts()`
    yields every route with its full path (prefix included), tags and dependency
    tree; plain `APIRoute`s (declared directly on the app) are used as they are.
    That wrapper API is FastAPI-internal, so tests/test_role_permissions.py pins
    known routes and gates: an upgrade that changes it fails there, loudly, not
    silently on the Director's screen."""
    from fastapi.routing import _IncludedRouter

    for route in routes:
        if isinstance(route, _IncludedRouter):
            yield from route.effective_route_contexts()
        elif isinstance(route, APIRoute):
            yield route


def _walk(dependant):
    """Every dependency call in a route's dependency tree, nested ones included --
    require_roles' own dependency depends on get_current_user, so a role-gated
    route shows both."""
    for dep in dependant.dependencies:
        yield dep.call
        yield from _walk(dep)


def _gate(route) -> tuple[list[str] | None, bool]:
    """(roles the route's role gate admits, or None if it has no role gate;
    whether the route needs any sign-in). If a route somehow carries more than one
    role gate the most restrictive applies, so the intersection is reported."""
    admitted: set[str] | None = None
    needs_login = False
    for call in _walk(route.dependant):
        roles = getattr(call, "allowed_roles", None)
        if roles is not None:
            admitted = set(roles) if admitted is None else admitted & set(roles)
        if call is get_current_user:
            needs_login = True
    if admitted is None:
        return None, needs_login
    return [role for role in ROLE_ORDER if role in admitted], True


def _label(route) -> str:
    if route.name in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[route.name]
    words = route.name.replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def build_role_permissions(routes) -> RolePermissionsOut:
    areas: dict[str, dict[tuple[str, ...], list[RouteItemOut]]] = {}
    ungated: list[UngatedRouteOut] = []
    gated_count = 0
    for route in _flatten(routes):
        if not route.include_in_schema:
            continue
        roles, needs_login = _gate(route)
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            item = RouteItemOut(method=method, path=route.path, label=_label(route))
            if roles is None:
                ungated.append(
                    UngatedRouteOut(**item.model_dump(), access="any_signed_in" if needs_login else "public")
                )
                continue
            gated_count += 1
            area = route.tags[0] if route.tags else "other"
            areas.setdefault(area, {}).setdefault(tuple(roles), []).append(item)

    area_out = []
    for area in sorted(areas):
        groups = [
            GroupOut(roles=list(roles), items=sorted(items, key=lambda i: (i.path, i.method)))
            for roles, items in sorted(areas[area].items(), key=lambda kv: (-len(kv[0]), kv[0]))
        ]
        area_out.append(AreaOut(area=area, groups=groups))
    ungated.sort(key=lambda i: (i.path, i.method))
    return RolePermissionsOut(roles=ROLE_ORDER, gated_route_count=gated_count, areas=area_out, ungated=ungated)


@router.get("/role-permissions", response_model=RolePermissionsOut)
def get_role_permissions(request: Request, current_user=Depends(require_roles("director"))):
    return build_role_permissions(request.app.routes)
