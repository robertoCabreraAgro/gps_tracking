from odoo import fields, models, api
from psycopg2.extensions import AsIs
import logging

_logger = logging.getLogger(__name__)

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
    
    def refresh_materialized_view(self):
        """Method called by the UI action to refresh the materialized view"""
        _logger.info("Refreshing materialized view fleet_vehicle_loan_report")
        try:
            self.env.cr.execute("REFRESH MATERIALIZED VIEW fleet_vehicle_loan_report")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Éxito',
                    'message': 'La vista materializada se ha actualizado correctamente',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f"Error refreshing materialized view: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al actualizar la vista materializada: {e}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def init(self):
        """Initialize the materialized view"""
        tools = self.env['ir.module.module']._get_module_tools()
        self.env.cr.execute("SELECT to_regclass('fleet_vehicle_loan_report')")
        if not self.env.cr.fetchone()[0]:
            _logger.info("Creating materialized view fleet_vehicle_loan_report")
            query = self._query()
            try:
                self.env.cr.execute(f"""
                    CREATE MATERIALIZED VIEW fleet_vehicle_loan_report AS (
                        {query}
                    ) WITH DATA
                """)
                self.env.cr.execute("CREATE UNIQUE INDEX fleet_vehicle_loan_report_id_idx ON fleet_vehicle_loan_report (id)")
                _logger.info("Successfully created materialized view fleet_vehicle_loan_report")
            except Exception as e:
                _logger.error(f"Error creating materialized view: {e}")
                # Try to create a regular view instead as fallback
                try:
                    tools.drop_view_if_exists(self.env.cr, 'fleet_vehicle_loan_report')
                    self.env.cr.execute(f"""
                        CREATE OR REPLACE VIEW fleet_vehicle_loan_report AS (
                            {query}
                        )
                    """)
                    _logger.info("Created regular view as fallback")
                except Exception as e2:
                    _logger.error(f"Error creating fallback view: {e2}")
        else:
            # View already exists, try to refresh it
            try:
                self.env.cr.execute("REFRESH MATERIALIZED VIEW fleet_vehicle_loan_report")
                _logger.info("Refreshed existing materialized view")
            except Exception as e:
                _logger.error(f"Error refreshing existing materialized view: {e}")