"""Fase 6 en Databricks: tablas y vistas del ciclo de prevenciones, y la alerta SQL que manda los correos.

Uso:
    python databricks/fase6_preparar.py preparar
    python databricks/fase6_preparar.py reiniciar     # borra avisos, oficios, tareas y alertas (demo en cero)
    python databricks/fase6_preparar.py probar_correo # manda una alerta de prueba a tu correo
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for p in ("databricks", "app/comun", "compartido"):
    sys.path.insert(0, str(RAIZ / p))
import fase2_normas as F  # noqa: E402
from databricks.sdk.service import jobs, sql as dsql  # noqa: E402
from datos_databricks import NOMBRE_JOB_ALERTAS, DatosDatabricks  # noqa: E402

CAT = F.CAT
CORREO = "obed.valle@dataiq.com.mx"
NOMBRE_ALERTA = "obed_farma · alertas de prevenciones"
w = F.w


def preparar():
    texto = (RAIZ / "compartido" / "sql" / "prevenciones.sql").read_text(encoding="utf-8")
    texto = re.sub(r"--[^\n]*", "", texto).replace("{L}", f"{CAT}.limpio").replace("{N}", f"{CAT}.negocio").replace("{A}", f"{CAT}.app")
    for s in [x.strip() for x in texto.split(";") if x.strip()]:
        F.sql(s)
    # alerta SQL (formato con consulta guardada, el que acepta la tarea de alerta de un job):
    # dispara si hay alertas sin enviar y manda por correo la tabla de asuntos
    for a in w.alerts_v2.list_alerts():          # limpia el intento previo con el formato v2
        if a.display_name == NOMBRE_ALERTA:
            w.alerts_v2.trash_alert(a.id)
    consulta_sql = (f"SELECT asunto AS alerta, tramite_id AS tramite, creada_en, COUNT(*) OVER () AS pendientes "
                    f"FROM {CAT}.app.alertas WHERE enviada_en IS NULL ORDER BY creada_en")
    consulta = next((x for x in w.queries.list() if x.display_name == NOMBRE_ALERTA), None)
    if consulta:
        w.queries.update(consulta.id, update_mask="query_text,warehouse_id",
                         query=dsql.UpdateQueryRequestQuery(query_text=consulta_sql, warehouse_id=F.WAREHOUSE))
    else:
        consulta = w.queries.create(query=dsql.CreateQueryRequestQuery(display_name=NOMBRE_ALERTA, query_text=consulta_sql,
                                                                      warehouse_id=F.WAREHOUSE))
    condicion = dsql.AlertCondition(op=dsql.AlertOperator.GREATER_THAN,
                                    operand=dsql.AlertConditionOperand(column=dsql.AlertOperandColumn(name="pendientes")),
                                    threshold=dsql.AlertConditionThreshold(value=dsql.AlertOperandValue(double_value=0)),
                                    empty_result_state=dsql.AlertState.OK)
    cuerpo = ("<p>Hay alertas nuevas del ciclo de prevenciones (demo Obed Farmacéutica · Laboratorios Altamira, ficticio):</p>"
              "{{QUERY_RESULT_TABLE}}<p>Revise la vista de prevenciones en la app.</p>")
    alerta = next((x for x in w.alerts.list() if x.display_name == NOMBRE_ALERTA), None)
    if alerta:
        w.alerts.update(alerta.id, update_mask="condition,custom_body,custom_subject,seconds_to_retrigger,query_id",
                        alert=dsql.UpdateAlertRequestAlert(condition=condicion, custom_body=cuerpo, query_id=consulta.id,
                                                           custom_subject="[COFEPRIS · Altamira] Alertas de prevenciones",
                                                           seconds_to_retrigger=1))
    else:
        alerta = w.alerts.create(alert=dsql.CreateAlertRequestAlert(display_name=NOMBRE_ALERTA, query_id=consulta.id,
                                                                    condition=condicion, custom_body=cuerpo, seconds_to_retrigger=1,
                                                                    custom_subject="[COFEPRIS · Altamira] Alertas de prevenciones"))
    job = next((j for j in w.jobs.list(name=NOMBRE_JOB_ALERTAS)), None)
    tarea = jobs.Task(task_key="alerta_correo", sql_task=jobs.SqlTask(
        warehouse_id=F.WAREHOUSE, alert=jobs.SqlTaskAlert(alert_id=alerta.id, subscriptions=[jobs.SqlTaskSubscription(user_name=CORREO)])))
    if job:
        w.jobs.reset(job.job_id, jobs.JobSettings(name=NOMBRE_JOB_ALERTAS, tasks=[tarea]))
    else:
        w.jobs.create(name=NOMBRE_JOB_ALERTAS, tasks=[tarea])
    print(f"  tablas y vistas listas · alerta {alerta.id} · job {NOMBRE_JOB_ALERTAS}")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "preparar"
    d = DatosDatabricks(w, F.WAREHOUSE)
    try:
        if accion == "preparar":
            preparar()
        elif accion == "reiniciar":
            d.reiniciar_prevenciones(); print("  prevenciones en cero")
        elif accion == "probar_correo":
            d._alerta("Prueba", "TR-2026-032", "prueba", "[Prueba] Correo de alertas desde Databricks",
                      "Prueba del canal de alertas de la demo Obed Farmacéutica.")
            print("  enviadas:", d.enviar_correos())
    finally:
        w.warehouses.stop(F.WAREHOUSE)


if __name__ == "__main__":
    main()
