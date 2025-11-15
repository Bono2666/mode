# from odoo import http


# class Employees(http.Controller):
#     @http.route('/employees/employees', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/employees/employees/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('employees.listing', {
#             'root': '/employees/employees',
#             'objects': http.request.env['employees.employees'].search([]),
#         })

#     @http.route('/employees/employees/objects/<model("employees.employees"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('employees.object', {
#             'object': obj
#         })

