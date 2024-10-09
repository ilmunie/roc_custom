from odoo import fields, models, api, SUPERUSER_ID
import json

class TechnicalJobActionDoneConfig(models.Model):
    _name = 'technical.job.action.done.config'

    def open_write_assistant(self):
        ctx = {'rec_field': self.rec_field.id, 'rec_field_domain': self.rec_field_domain, 'config_id': self._origin.id}
        id = self.env['technical.job.action.done.wizard'].create(ctx).id
        return {
            'name': "Configuracion finalizacion tareas",
            'res_model': 'technical.job.action.done.wizard',
            'type': 'ir.actions.act_window',
            'res_id': id,
            'target': 'new',
            "view_type": "form",
            "view_mode": "form",
        }


    domain_condition = fields.Char(string="Condicion aplicación")
    config_id = fields.Many2one('technical.job.assistant.config')
    model_name = fields.Char(related="config_id.model_name", string="Modelo")
    rec_field = fields.Many2one('ir.model.fields', string="Campo")
    write_vals = fields.Char(string="Valor escritura")

    @api.depends('rec_field')
    def get_result_resume(self):
        for record in self:
            record.result_resume = False

    result_resume = fields.Char(compute=get_result_resume, store=True, string="Resumen escritura")

    @api.depends('config_id', 'config_id.model_id')
    def get_rec_field_domain(self):
        for record in self:
            res = []
            res.append(('model_id','=', record.config_id.model_id.id))
            res.append(('readonly','=', False))
            record.rec_field_domain = json.dumps(res)

    rec_field_domain = fields.Char(compute=get_rec_field_domain, store=True)

class TechnicalJobAssistantConfig(models.Model):
    _inherit = 'technical.job.assistant.config'

    action_done_line_ids = fields.One2many('technical.job.action.done.config', 'config_id', string="Configuracion escritura")


class TechnicalJobActionDoneWizard(models.TransientModel):
    _name = 'technical.job.action.done.wizard'


    def action_done(self):
        wr_vals = "{"
        if self.rec_field_ttype == 'many2many':
            if self.many2many_write_type == 'delete':
                wr_vals += f"""'{self.rec_field.name}': [(5,)]"""
            elif self.many2many_write_type == 'replace':
                wr_vals += f"""'{self.rec_field.name}': [(6, 0, ({','.join(self.many2many_value.mapped('model_reference_id'))}))]"""
            elif self.many2many_write_type == 'add':
                m2m_val = "["
                for val in self.many2many_value:
                    m2m_val +=  f"(4, {val.model_reference_id}),"
                m2m_val += "]"
                wr_vals += f"""'{self.rec_field.name}': {m2m_val}"""
        elif self.rec_field_ttype == 'many2one':
            if self.many2one_value:
                wr_vals += f"""'{self.rec_field.name}': {self.many2one_value.model_reference_id}"""
            else:
                wr_vals += f"""'{self.rec_field.name}': False"""
        elif self.rec_field_ttype == 'selection':
            if self.many2one_value:
                wr_vals += f"""'{self.rec_field.name}': {self.selection_value.name}"""
            else:
                wr_vals += f"""'{self.rec_field.name}': False"""
        elif self.rec_field_ttype == 'char':
            wr_vals += f"""'{self.rec_field.name}': {self.char_value}"""
        elif self.rec_field_ttype == 'text':
            wr_vals += f"""'{self.rec_field.name}': {self.text_value}"""
        elif self.rec_field_ttype == 'boolean':
            wr_vals += f"""'{self.rec_field.name}': {self.boolean_value}"""
        elif self.rec_field_ttype == 'date_value':
            wr_vals += f"""'{self.rec_field.name}': {self.date_value}"""
        elif self.rec_field_ttype == 'datetime':
            wr_vals += f"""'{self.rec_field.name}': {self.datetime_value}"""
        elif self.rec_field_ttype == 'float':
            wr_vals += f"""'{self.rec_field.name}': {self.float_value}"""
        elif self.rec_field_ttype == 'integer':
            wr_vals += f"""'{self.rec_field.name}': {self.integer_value}"""

        wr_vals += "}"
        self.config_id.write({
            'rec_field': self.rec_field.id,
            'write_vals': wr_vals,
            'result_resume': False,
        })
        return False

    config_id = fields.Many2one('technical.job.action.done.config')

    rec_field = fields.Many2one('ir.model.fields', string="Campo escritura")
    rec_field_domain = fields.Char()
    rec_field_ttype = fields.Selection(related="rec_field.ttype")
    @api.onchange('rec_field')
    def onchange_rec_field(self):
        self.ensure_one()
        query = """
            DELETE FROM technical_job_action_done_wizard_values
        """
        self.env.cr.execute(query)
        if self.rec_field.ttype in ('many2one', 'many2many', 'one2many'):
            # Get the table name dynamically
            table_name = self.rec_field.relation.replace('.', '_')

            # Build the query by injecting the table name
            query = """
                INSERT INTO technical_job_action_done_wizard_values
                (wiz_id, name, model_reference_id)
                SELECT %s, name, id
                FROM {}
            """.format(table_name)

            self.env.cr.execute(query, (self._origin.id,))
        elif self.rec_field.ttype == 'selection':
            #query to create available_values for selection fields
            vals = []
            for selection_val in self.rec_field.selection_ids:
                vals.append((0, 0, {'model_reference_id': selection_val.value, 'name': selection_val.name}))
            self.available_value_ids = vals

    available_value_ids = fields.One2many('technical.job.action.done.wizard.values', 'wiz_id')

    char_value = fields.Char(string="Valor (Char)")
    text_value = fields.Text(string="Valor (Char)")
    boolean_value = fields.Boolean(string="Valor (Booleano)")
    date_value = fields.Date(string="Valor (Fecha)")
    datetime_value = fields.Datetime(string="Valor (Fecha y hora)")
    float_value = fields.Float(string="Valor (Float)")
    integer_value = fields.Integer(string="Valor (Entero)")

    @api.depends('available_value_ids')
    def get_value_domain(self):
        for record in self:
            res = []
            res.append(('wiz_id', '=', self._origin.id))
            record.values_domain = json.dumps(res)

    values_domain = fields.Char(compute=get_value_domain)
    many2many_value = fields.Many2many('technical.job.action.done.wizard.values', 'tj_adw_rel', 'wiz_id', 'val_id', string="Valor (m2m)")
    many2many_write_type = fields.Selection(selection=[('add', 'Agregar'), ('replace', 'Reemplazar'), ('delete', 'Eliminar')], string="Tipo escritura")

    many2one_value = fields.Many2one('technical.job.action.done.wizard.values', string="Valor (m2o)")
    selection_value = fields.Many2one('technical.job.action.done.wizard.values', string="Valor seleccion")



class TechnicalJobActionDoneWizardValues(models.TransientModel):
    _name = 'technical.job.action.done.wizard.values'

    name = fields.Char()
    model_reference_id = fields.Char()
    wiz_id = fields.Many2one('technical.job.action.done.wizard')
