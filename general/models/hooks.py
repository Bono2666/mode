from odoo import api, SUPERUSER_ID


def uninstall_hook_cleanup_users(*args, **kwargs):
    # Ambil Environment dari args (berdasarkan log DEBUG Anda sebelumnya)
    if args and isinstance(args[0], api.Environment):
        env = args[0](user=SUPERUSER_ID)
    else:
        cr = args[0] if args else kwargs.get('cr')
        if not cr:
            return
        env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Identifikasi User yang HARUS DILINDUNGI
    # Proteksi berdasarkan XML ID
    xml_ids = [
        'base.user_admin',
        'base.public_user',
        'base.default_user_template',
        'base.template_portal_user',
        'base.user_root'
    ]

    protected_ids = [1]  # ID 1 selalu OdooBot
    for x_id in xml_ids:
        res = env.ref(x_id, raise_if_not_found=False)
        if res:
            protected_ids.append(res.id)

    # 2. Cari User yang akan diproses (dengan proteksi tambahan lewat NAMA)
    # Kita tambahkan filter nama 'Template' dan 'Public' untuk memastikan tidak terhapus
    users_to_process = env['res.users'].sudo().with_context(active_test=False).search([
        ('id', 'not in', protected_ids),
        ('name', 'not ilike', 'Template'),
        ('name', 'not ilike', 'Public User')
    ])

    if users_to_process:
        print(f"DEBUG: Memproses {len(users_to_process)} user...")
        partner_ids = users_to_process.mapped('partner_id')

        # --- LANGKAH KRUSIAL: URUTAN ---

        # A. Nonaktifkan User TERLEBIH DAHULU (Ubah status di DB)
        # Kita gunakan flush() agar Odoo segera menulis perubahan ke DB sebelum lanjut
        users_to_process.write({'active': False})
        env.flush_all()

        # B. Sekarang baru coba nonaktifkan Partner
        if partner_ids:
            try:
                # Coba hapus permanen jika memungkinkan
                # Hanya untuk partner yang tidak terhubung ke user aktif manapun
                partner_ids.write({'active': False})
                env.flush_all()
                print("DEBUG: Partner berhasil di-archive.")
            except Exception as e:
                print(
                    f"DEBUG: Gagal archive partner, kemungkinan ada relasi lain: {e}")

        # C. Coba hapus permanen User (Jika tidak ada transaksi)
        try:
            users_to_process.unlink()
            print("DEBUG: User berhasil dihapus permanen.")
        except Exception:
            print("DEBUG: User hanya dinonaktifkan karena memiliki histori transaksi.")
