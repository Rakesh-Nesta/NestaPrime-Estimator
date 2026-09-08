from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    accessories,
    athletics,
    attachments,
    audit_log,
    auth,
    client_signatories,
    clients,
    documents,
    exports,
    flooring,
    gym,
    hvac,
    lighting,
    messages,
    overheads,
    pdf_documents,
    play_equipment,
    pool,
    pricing,
    projects,
    purchase_orders,
    rate_items,
    regional_multipliers,
    reports,
    schedule,
    scope_items,
    settings,
    site_works,
    skip_requests,
    sports,
    structures,
    tender,
    vendors,
    work_orders,
)

app = FastAPI(title="NestaPrime Estimator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(client_signatories.client_signatories_router)
app.include_router(projects.router)
app.include_router(regional_multipliers.router)
app.include_router(sports.sports_router)
app.include_router(sports.project_sports_router)
app.include_router(scope_items.scope_items_router)
app.include_router(scope_items.project_scope_items_router)
app.include_router(rate_items.labour_categories_router)
app.include_router(rate_items.rate_items_router)
app.include_router(pricing.margin_policies_router)
app.include_router(pricing.sport_margin_policies_router)
app.include_router(pricing.pricing_router)
app.include_router(tender.tender_details_router)
app.include_router(tender.tender_calc_router)
app.include_router(documents.cost_sheets_router)
app.include_router(documents.estimates_router)
app.include_router(documents.quotations_router)
app.include_router(schedule.schedule_router)
app.include_router(settings.settings_router)
app.include_router(settings.overrides_router)
app.include_router(reports.router)
app.include_router(structures.structures_router)
app.include_router(site_works.site_works_router)
app.include_router(flooring.flooring_router)
app.include_router(lighting.lighting_router)
app.include_router(hvac.hvac_router)
app.include_router(gym.gym_router)
app.include_router(pool.pool_router)
app.include_router(accessories.accessories_router)
app.include_router(athletics.athletics_router)
app.include_router(play_equipment.play_equipment_router)
app.include_router(overheads.overheads_router)
app.include_router(exports.exports_router)
app.include_router(attachments.attachments_router)
app.include_router(audit_log.audit_log_router)
app.include_router(messages.messages_router)
app.include_router(pdf_documents.pdf_documents_router)
app.include_router(vendors.vendors_router)
app.include_router(purchase_orders.purchase_orders_router)
app.include_router(work_orders.work_orders_router)
app.include_router(skip_requests.skip_requests_router)


@app.get("/health")
def health():
    return {"status": "ok"}
