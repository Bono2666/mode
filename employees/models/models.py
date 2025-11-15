from odoo import models, fields, api


class employees(models.Model):
    _name = 'employees.employees'
    _description = 'employees.employees'

    employeeid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'employees.employees'), string="Employee ID")
    employeenm = fields.Char(string="Employee Name")
    position_id = fields.Many2one(
        comodel_name='general.position', string='Job Position')
    department_id = fields.Many2one(
        comodel_name='general.department', string='Department')
    salescode = fields.Char(string="Sales Code")
