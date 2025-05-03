from odoo import fields, models
from psycopg2.extensions import AsIs

class FleetVehicleLoanReport(models.Model):
    _name = 'fleet.vehicle.loan.report'
    _description = 'Reporte de préstamos de vehículos aprobados'
    _auto = False  # No crea una tabla, se basa en una vista materializada
    
    username = fields.Char(string='Solicitante', readonly=True)
    vehiculo = fields.Char(string='Vehículo', readonly=True)
    odometer_start = fields.Float(string='Odómetro inicial', readonly=True)
    odometer_end = fields.Float(string='Odómetro final', readonly=True)
    date_start = fields.Datetime(string='Fecha inicio', readonly=True)
    weekday_start = fields.Char(string='Día inicio', readonly=True)
    date_end = fields.Datetime(string='Fecha fin', readonly=True)
    weekday_end = fields.Char(string='Día fin', readonly=True)
    
    def _query(self):
        return """
            SELECT 
                ar.id, 
                rp.name AS username, 
                fv.name AS vehiculo, 
                ar.odometer AS odometer_start,
                (SELECT MIN(ar2.odometer) 
                FROM approval_request ar2 
                WHERE ar2.request_owner_id = ar.request_owner_id 
                AND ar2.vehicle_id = ar.vehicle_id 
                AND ar2.odometer > ar.odometer) AS odometer_end,
                ar.date_start AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City' AS date_start, 
                CASE EXTRACT(DOW FROM ar.date_start AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City') 
                    WHEN 0 THEN 'Domingo' 
                    WHEN 1 THEN 'Lunes' 
                    WHEN 2 THEN 'Martes' 
                    WHEN 3 THEN 'Miércoles' 
                    WHEN 4 THEN 'Jueves' 
                    WHEN 5 THEN 'Viernes' 
                    WHEN 6 THEN 'Sábado' 
                END AS weekday_start, 
                ar.date_end AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City' AS date_end, 
                CASE EXTRACT(DOW FROM ar.date_end AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City') 
                    WHEN 0 THEN 'Domingo' 
                    WHEN 1 THEN 'Lunes' 
                    WHEN 2 THEN 'Martes' 
                    WHEN 3 THEN 'Miércoles' 
                    WHEN 4 THEN 'Jueves' 
                    WHEN 5 THEN 'Viernes' 
                    WHEN 6 THEN 'Sábado' 
                END AS weekday_end 
            FROM 
                approval_request ar 
            JOIN 
                res_users ru ON ar.request_owner_id = ru.id 
            JOIN 
                res_partner rp ON ru.partner_id = rp.id 
            LEFT JOIN 
                fleet_vehicle fv ON ar.vehicle_id = fv.id 
            WHERE 
                ar.category_id = 108 
                AND ar.request_status = 'approved'
            ORDER BY ar.date_start desc
        """
    
    def _check_is_populated(self, table):
        self._cr.execute(
            f"SELECT relispopulated FROM pg_class WHERE relname = '{table}' and relkind = 'm'"
        )
        res = self._cr.fetchone()
        return res and res[0]

    def refresh_concurrently(self):
        table = AsIs(self._table)
        if not self._check_is_populated(table):
            self._cr.execute(f"REFRESH MATERIALIZED VIEW {table}")
            return

        self._cr.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {table}")

    def init(self):
        table = AsIs(self._table)
        query = AsIs(self._query())
        self._cr.execute(f"DROP MATERIALIZED view IF EXISTS {table} CASCADE")
        if self._context.get("with_data"):
            # Crea la vista materializada con datos
            self._cr.execute(f"CREATE MATERIALIZED VIEW {table} AS ({query})")
        else:
            # Crea la vista materializada sin datos (para una actualización más rápida del módulo)
            self._cr.execute(
                f"CREATE MATERIALIZED VIEW {table} AS ({query}) WITH NO DATA"
            )
        self._cr.execute(f"CREATE UNIQUE INDEX {table}_id_idx ON {table} (id)")