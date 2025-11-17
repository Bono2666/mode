from odoo import models, fields, api


class employees(models.Model):
    _name = 'employees.employees'
    _description = 'employees.employees'

    employee_id = fields.Char(string="Employee ID",
                              primary_key=True, readonly=True, unique=True, auto_save=False)
    employee_name = fields.Char(string="Employee Name", auto_save=False)
    position_id = fields.Many2one(
        comodel_name='general.position', string='Job Position', auto_save=False)
    department_id = fields.Many2one(
        comodel_name='general.department', string='Department', auto_save=False)
    salescode = fields.Char(string="Sales Code", auto_save=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('employee_id'):
                    v['employee_id'] = self.env['ir.sequence'].next_by_code(
                        'employees.employees.sequence')
            return super(employees, self).create(vals)
        if not vals.get('employee_id'):
            vals['employee_id'] = self.env['ir.sequence'].next_by_code(
                'employees.employees.sequence')
        return super(employees, self).create(vals)
