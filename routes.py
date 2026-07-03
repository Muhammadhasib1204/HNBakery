from flask import render_template, request, redirect, url_for, session, flash, jsonify
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Wajib agar matplotlib tidak error di server Flask
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from sklearn.tree import DecisionTreeRegressor
from models import get_db_connection

def init_routes(app):
    
    # ==========================================
    # 1. AUTHENTICATION (LOGIN/LOGOUT)
    # ==========================================
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'loggedin' in session:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM admin WHERE username = %s AND password = %s', (username, password))
            admin = cursor.fetchone()
            conn.close()
            if admin:
                session['loggedin'] = True
                session['id'] = admin['id']
                session['username'] = admin['username']
                return redirect(url_for('dashboard'))
            else:
                flash('Username atau Password salah!')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    # ==========================================
    # 2. DASHBOARD
    # ==========================================
    @app.route('/')
    def dashboard():
        if 'loggedin' not in session:
            return redirect(url_for('login'))
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT COUNT(*) as total FROM data_roti')
        total_roti = cursor.fetchone()['total']
        cursor.execute('SELECT COUNT(*) as total FROM data_penjualan')
        total_penjualan = cursor.fetchone()['total']
        conn.close()
        return render_template('dashboard.html', total_roti=total_roti, total_penjualan=total_penjualan)

    # ==========================================
    # 3. CRUD DATA PRODUK
    # ==========================================
    @app.route('/data_produk')
    def data_produk():
        if 'loggedin' not in session:
            return redirect(url_for('login'))
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM data_roti ORDER BY id DESC')
        semua_roti = cursor.fetchall()
        conn.close()
        return render_template('data_produk.html', produk=semua_roti)

    @app.route('/tambah_produk', methods=['POST'])
    def tambah_produk():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO data_roti (nama_roti, kategori, harga, stok) VALUES (%s, %s, %s, %s)', 
                       (request.form['nama_roti'], request.form['kategori'], request.form['harga'], request.form['stok']))
        conn.commit()
        conn.close()
        flash('Produk berhasil ditambahkan!')
        return redirect(url_for('data_produk'))

    @app.route('/edit_produk/<int:id>', methods=['POST'])
    def edit_produk(id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE data_roti SET nama_roti=%s, kategori=%s, harga=%s, stok=%s WHERE id=%s', 
                       (request.form['nama_roti'], request.form['kategori'], request.form['harga'], request.form['stok'], id))
        conn.commit()
        conn.close()
        flash('Produk berhasil diperbarui!')
        return redirect(url_for('data_produk'))

    @app.route('/hapus_produk/<int:id>')
    def hapus_produk(id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM data_roti WHERE id=%s', (id,))
        conn.commit()
        conn.close()
        return redirect(url_for('data_produk'))

    # ==========================================
    # 4. DATA PENJUALAN, IMPORT CSV & CRUD
    # ==========================================
    @app.route('/data_penjualan')
    def data_penjualan():
        if 'loggedin' not in session:
            return redirect(url_for('login'))
        
        search_year = request.args.get('search_year', '')
        page = request.args.get('page', 1, type=int)
        per_page = 10
        offset = (page - 1) * per_page

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if search_year:
            query = "SELECT * FROM data_penjualan WHERE YEAR(tanggal) = %s ORDER BY tanggal ASC LIMIT %s OFFSET %s"
            params = (search_year, per_page, offset)
        else:
            query = "SELECT * FROM data_penjualan ORDER BY tanggal ASC LIMIT %s OFFSET %s"
            params = (per_page, offset)
        
        cursor.execute(query, params)
        penjualan = cursor.fetchall()
        
        cursor.execute('SELECT nama_roti FROM data_roti')
        roti_list = cursor.fetchall()
        conn.close()
        
        return render_template('data_penjualan.html', 
                               penjualan=penjualan, 
                               roti_list=roti_list, 
                               page=page, 
                               per_page=per_page)

    @app.route('/import_csv', methods=['POST'])
    def import_csv():
        if 'loggedin' not in session:
            return redirect(url_for('login'))
    
        file = request.files['file_csv']
        if file.filename != '':
            try:
                df = pd.read_csv(file, sep=';') 
                df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('\r', '')
        
                if 'jumlah_terjual' not in df.columns:
                    for col in df.columns:
                        if 'terjual' in col:
                            df.rename(columns={col: 'jumlah_terjual'}, inplace=True)
                            break
        
            # === TAHAP BERSIHKAN DATA HARGA, STOK & TERJUAL (REVISI CLEANING) ===
                df['jumlah_terjual'] = df['jumlah_terjual'].astype(str).str.replace(r'\D', '', regex=True)
                df['jumlah_terjual'] = pd.to_numeric(df['jumlah_terjual'], errors='coerce').fillna(0).astype(int)
        
                df['harga'] = df['harga'].astype(str).str.replace('Rp', '', regex=False)
                df['harga'] = df['harga'].str.replace('.', '', regex=False)
                df['harga'] = df['harga'].str.replace(r'\D', '', regex=True)
                df['harga'] = pd.to_numeric(df['harga'], errors='coerce').fillna(0).astype(int)
        
                df['stok'] = df['stok'].astype(str).str.replace(r'\D', '', regex=True)
                df['stok'] = pd.to_numeric(df['stok'], errors='coerce').fillna(0).astype(int)
        
            # Ubah string ke format Datetime
                df['tanggal'] = pd.to_datetime(df['tanggal'], format='%d/%m/%Y', errors='coerce')
                df['is_weekend'] = df['tanggal'].dt.dayofweek.apply(lambda x: 1 if x >= 5 else 0)
                df['is_weekday'] = df['tanggal'].dt.dayofweek.apply(lambda x: 1 if x < 5 else 0)
        
            # Format ke string standar MySQL
                df['tanggal'] = df['tanggal'].dt.strftime('%Y-%m-%d')
                df = df.dropna(subset=['tanggal'])

                conn = get_db_connection()
                cursor = conn.cursor()
        
                jumlah_masuk = 0
                jumlah_skip = 0  # Counter untuk mencatat data duplikat yang dilewati
            
                for _, row in df.iterrows():
                # === PROSES CEK DUPLIKAT DATA ===
                # Cek apakah tanggal dan jenis roti ini sudah pernah diinsert sebelumnya
                    cursor.execute('''
                        SELECT COUNT(*) FROM data_penjualan 
                        WHERE tanggal = %s AND jenis_roti = %s
                    ''', (row['tanggal'], row['jenis_roti']))
                
                    exists = cursor.fetchone()[0]
                
                    if exists > 0:
                        jumlah_skip += 1
                        continue  # Lewati baris ini dan lanjut ke baris CSV berikutnya
                
                # Jika belum ada, lakukan INSERT seperti biasa
                    cursor.execute('''
                        INSERT INTO data_penjualan 
                        (tanggal, jenis_roti, harga, stok, promo, jumlah_terjual, is_weekend, is_weekday) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        row['tanggal'], row['jenis_roti'], row['harga'], 
                        row['stok'], row['promo'], row['jumlah_terjual'],
                        row['is_weekend'], row['is_weekday']
                    ))
                    jumlah_masuk += 1
        
                conn.commit()
                conn.close()
            
            # Berikan notifikasi flash yang lebih informatif ke user
                if jumlah_skip > 0:
                    flash(f'Impor selesai! {jumlah_masuk} data berhasil masuk, dan {jumlah_skip} data duplikat otomatis dilewati.')
                else:
                    flash(f'Sukses! Semua data ({jumlah_masuk} baris) berhasil diimpor dan dibersihkan.')
        
            except Exception as e:
                flash(f"Error saat import CSV: {e}")
        
        return redirect(url_for('data_penjualan'))

    @app.route('/tambah_penjualan', methods=['POST'])
    def tambah_penjualan():
        if 'loggedin' not in session: 
            return redirect(url_for('login'))
    
        tanggal = request.form['tanggal']
        jenis_roti = request.form['jenis_roti']
        jumlah_terjual = int(request.form['jumlah_terjual'])

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
    
        try:
        # AMBIL HARGA & STOK LANGSUNG DARI MASTER DATA (FIX PATEN)
            cursor.execute('SELECT harga, stok FROM data_roti WHERE nama_roti = %s', (jenis_roti,))
            roti = cursor.fetchone()
        
            if not roti:
                flash('Varian produk roti tidak ditemukan!')
                return redirect(url_for('data_penjualan'))
            
            harga_fix = roti['harga'] # Harga dikunci dari database master
            stok_master_sekarang = roti['stok']
        
            if stok_master_sekarang < jumlah_terjual:
                flash(f'Gagal! Stok Master tidak cukup. Stok saat ini hanya {stok_master_sekarang} pcs.')
                return redirect(url_for('data_penjualan'))

        # Hitung sisa stok setelah dikurangi penjualan
            stok_harian_baru = stok_master_sekarang - jumlah_terjual
        
        # Update stok master di tabel produk
            cursor.execute('UPDATE data_roti SET stok = %s WHERE nama_roti = %s', (stok_harian_baru, jenis_roti))
        
        # Simpan transaksi ke tabel penjualan dengan harga paten
            cursor.execute('''
                INSERT INTO data_penjualan (tanggal, jenis_roti, harga, stok, promo, jumlah_terjual) 
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (tanggal, jenis_roti, harga_fix, stok_harian_baru, request.form['promo'], jumlah_terjual))
        
            conn.commit()
            flash('Data Transaksi Berhasil Ditambah, Harga Otomatis Match & Stok Dikurangi!')
        
        except Exception as e:
            conn.rollback()
            flash(f'Terjadi kesalahan saat tambah data: {str(e)}')
        finally:
            conn.close()
        
        return redirect(url_for('data_penjualan'))

    @app.route('/edit_penjualan/<int:id>', methods=['POST'])
    def edit_penjualan(id):
        if 'loggedin' not in session:
            return redirect(url_for('login'))
        
        tanggal = request.form['tanggal']
        jenis_roti = request.form['jenis_roti']
        promo = request.form['promo']
        jumlah_baru = int(request.form['jumlah_terjual'])

        date_obj = pd.to_datetime(tanggal)
        is_weekend = 1 if date_obj.dayofweek >= 5 else 0
        is_weekday = 1 if date_obj.dayofweek < 5 else 0

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
    
        try:
        # 1. Ambil data transaksi lama untuk proses restore stok harian
            cursor.execute('SELECT jenis_roti, jumlah_terjual, stok FROM data_penjualan WHERE id = %s', (id,))
            transaksi_lama = cursor.fetchone()
        
            if transaksi_lama:
                jumlah_lama = transaksi_lama['jumlah_terjual']
                stok_harian_lama = transaksi_lama['stok']
                roti_lama = transaksi_lama['jenis_roti']
            
            # Ambil data master roti yang baru dipilih untuk mendapatkan harga fix terbarunya
                cursor.execute('SELECT harga, stok FROM data_roti WHERE nama_roti = %s', (jenis_roti,))
                roti_master_baru = cursor.fetchone()
                harga_fix_baru = roti_master_baru['harga']
            
            # Kembalikan stok lama terlebih dahulu
                stok_awal_restore = stok_harian_lama + jumlah_lama
            
                if roti_lama == jenis_roti:
                    stok_harian_baru = stok_awal_restore - jumlah_baru
                    if stok_awal_restore < jumlah_baru:
                        flash(f'Gagal Ubah! Stok Master hasil restore ({stok_awal_restore} pcs) tidak mencukupi.')
                        return redirect(url_for('data_penjualan'))
                
                    cursor.execute('UPDATE data_roti SET stok = %s WHERE nama_roti = %s', (stok_harian_baru, jenis_roti))
                else:
                # Jika user mengganti jenis varian produk roti saat edit
                    cursor.execute('UPDATE data_roti SET stok = stok + %s WHERE nama_roti = %s', (jumlah_lama, roti_lama))
                
                    stok_master_roti_baru = roti_master_baru['stok']
                    stok_harian_baru = stok_master_roti_baru - jumlah_baru
                    cursor.execute('UPDATE data_roti SET stok = %s WHERE nama_roti = %s', (stok_harian_baru, jenis_roti))

            # Update tabel penjualan dengan harga fix baru dan stok harian terhitung otomatis
                cursor.execute('''
                    UPDATE data_penjualan 
                    SET tanggal = %s, jenis_roti = %s, harga = %s, stok = %s, 
                        promo = %s, jumlah_terjual = %s, is_weekend = %s, is_weekday = %s
                    WHERE id = %s
                ''', (tanggal, jenis_roti, harga_fix_baru, stok_harian_baru, promo, jumlah_baru, is_weekend, is_weekday, id))
            
                conn.commit()
                flash('Data Penjualan berhasil diperbarui. Harga dan Stok disinkronkan otomatis!')
        
        except Exception as e:
            conn.rollback()
            flash(f'Terjadi kesalahan saat ubah data: {str(e)}')
        finally:
            conn.close()
        
        return redirect(url_for('data_penjualan'))

    @app.route('/hapus_penjualan/<int:id>', methods=['GET'])
    def hapus_penjualan(id):
        if 'loggedin' not in session:
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
    
        try:
        # 1. Ambil data transaksi yang akan dihapus untuk tahu jenis roti dan jumlah terjualnya
            cursor.execute('SELECT jenis_roti, jumlah_terjual FROM data_penjualan WHERE id = %s', (id,))
            transaksi = cursor.fetchone()
        
            if transaksi:
                jenis_roti = transaksi['jenis_roti']
                jumlah_batal_terjual = transaksi['jumlah_terjual']
            
            # 2. PERBAIKAN UTAMA: Ambil Stok Master Gudang yang ada SAAT INI di data_roti
                cursor.execute('SELECT stok FROM data_roti WHERE nama_roti = %s', (jenis_roti,))
                roti_master = cursor.fetchone()
            
                if roti_master:
                    stok_master_sekarang = roti_master['stok']
                
                # 3. Rumus Benar: Tambahkan jumlah batal terjual langsung ke stok gudang saat ini
                # Misal stok saat ini 25, lalu transaksi terjual 5 dihapus -> Stok Gudang jadi 25 + 5 = 30
                    stok_master_baru = stok_master_sekarang + jumlah_batal_terjual
                
                # 4. Update kembali ke master data_roti
                    cursor.execute('UPDATE data_roti SET stok = %s WHERE nama_roti = %s', 
                               (stok_master_baru, jenis_roti))
            
            # 5. Terakhir, hapus baris record dari tabel data_penjualan
                cursor.execute('DELETE FROM data_penjualan WHERE id = %s', (id,))
            
            conn.commit()
            flash('Data Transaksi berhasil dihapus dan stok master gudang telah di-restore dengan benar!')
        
        except Exception as e:
            conn.rollback()
            flash(f'Terjadi kesalahan saat hapus data: {str(e)}')
        finally:
            conn.close()
        
        return redirect(url_for('data_penjualan'))

    @app.route('/get_detail_roti/<string:nama_roti>', methods=['GET'])
    def get_detail_roti(nama_roti):
        if 'loggedin' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
    
        cursor.execute('SELECT harga, stok FROM data_roti WHERE nama_roti = %s', (nama_roti,))
        roti = cursor.fetchone()
        conn.close()
    
        if roti:
            return jsonify({
                'harga': roti['harga'],
                'stok': roti['stok']
            })
        else:
            return jsonify({'error': 'Roti tidak ditemukan'}), 404

    # ==========================================
    # 5. CORE ANALISIS GBDT & FORECASTING (2 MODE)
    # ==========================================
    @app.route('/analisis', methods=['GET', 'POST'])
    def analisis():
        if 'loggedin' not in session:
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT nama_roti FROM data_roti')
        roti_list = cursor.fetchall()

        if request.method == 'POST':
            jenis_roti = request.form['jenis_roti']
            resolusi_waktu = request.form['resolusi_waktu']
            
            # Menangkap tanggal target masa depan (Jika ada)
            start_date_pred = request.form.get('start_date')
            end_date_pred = request.form.get('end_date')

            # TAHAP 0: Ambil SELURUH data historis untuk Training (100% Historis)
            cursor.execute('''
                SELECT tanggal, harga, stok, promo, jumlah_terjual 
                FROM data_penjualan 
                WHERE jenis_roti = %s 
                ORDER BY tanggal ASC
            ''', (jenis_roti,))
            data = cursor.fetchall()
            
            if not data:
                conn.close()
                flash("Data historis tidak ditemukan untuk roti ini!")
                return redirect(url_for('analisis'))

            # TAHAP 1: PRA-PEMROSESAN & REKAYASA FITUR
            df = pd.DataFrame(data)
            df['tanggal'] = pd.to_datetime(df['tanggal'])
            df['is_weekend'] = df['tanggal'].dt.dayofweek.apply(lambda x: 1 if x >= 5 else 0)
            df['is_weekday'] = df['tanggal'].dt.dayofweek.apply(lambda x: 1 if x < 5 else 0)
            df['promo'] = df['promo'].apply(lambda x: 1 if x == 'Ya' else 0)
            df.set_index('tanggal', inplace=True)

            if resolusi_waktu == 'W':
                agg_funcs = {'harga': 'mean', 'stok': 'sum', 'promo': 'max', 'is_weekend': 'sum', 'is_weekday': 'sum', 'jumlah_terjual': 'sum'}
            else: 
                agg_funcs = {'harga': 'mean', 'stok': 'sum', 'promo': 'max', 'is_weekend': 'max', 'is_weekday': 'max', 'jumlah_terjual': 'sum'}

            df_resampled = df.resample(resolusi_waktu).agg(agg_funcs).fillna(0)

            if len(df_resampled) < 10:
                conn.close()
                flash("Data historis terlalu sedikit (min. 10 baris data)!")
                return redirect(url_for('analisis'))

            # TAHAP 2: TIME-SERIES SPLIT (80:20) UNTUK VALIDASI
            split_idx = int(len(df_resampled) * 0.8)
            train_df = df_resampled.iloc[:split_idx]
            test_df = df_resampled.iloc[split_idx:]

            fitur_cols = ['harga', 'stok', 'promo', 'is_weekend', 'is_weekday']
            X_train = train_df[fitur_cols].values
            y_train = train_df['jumlah_terjual'].values
            X_test = test_df[fitur_cols].values
            y_test_aktual = test_df['jumlah_terjual'].values

            # TAHAP 3: PELATIHAN GBDT CUSTOM
            n_estimators = 150 
            learning_rate = 0.05 
            models = []
            log_perhitungan = [] 
            
            f0 = np.median(y_train)
            F_train = np.full(len(y_train), f0) 

            for i in range(n_estimators):
                residual = y_train - F_train
                tree = DecisionTreeRegressor(max_depth=4, random_state=42)
                tree.fit(X_train, residual)
                h_m = tree.predict(X_train)
                
                log_perhitungan.append({
                    'iterasi': i + 1, 'f_awal': np.round(F_train[:5], 2).tolist(),
                    'residual': np.round(residual[:5], 2).tolist(), 'h_m': np.round(h_m[:5], 2).tolist(),
                    'f_akhir': np.round(F_train[:5] + (learning_rate * h_m[:5]), 2).tolist()
                })
                F_train += learning_rate * h_m
                models.append(tree)

            # TAHAP 4: BACKTESTING MAE
            F_test_pred = np.full(len(y_test_aktual), f0)
            for tree in models:
                F_test_pred += learning_rate * tree.predict(X_test)
            F_test_pred = np.round(F_test_pred).astype(int)
            
            detail_mae = []
            errors_for_mae = [] 
            for i in range(len(y_test_aktual)):
                aktual_val = int(y_test_aktual[i])
                pred_val = int(F_test_pred[i])
                err = abs(aktual_val - pred_val)
                errors_for_mae.append(err)
                
                if resolusi_waktu == 'D' and aktual_val == 0: continue
                detail_mae.append({'tanggal': test_df.index[i].strftime('%d/%m/%Y'), 'aktual': aktual_val, 'prediksi': pred_val, 'error': int(err)})
            
            mae_manual = np.mean(errors_for_mae)

            # TAHAP 5: FEATURE IMPORTANCE
            importances = np.mean([t.feature_importances_ for t in models], axis=0)
            feature_importance_list = [{'fitur': name.replace('_', ' ').title(), 'score': round(float(imp), 4)} for name, imp in zip(fitur_cols, importances)]
            feature_importance_list = sorted(feature_importance_list, key=lambda x: x['score'], reverse=True)

            # TAHAP 6: SISTEM PAKAR
            y_train_filter = y_train[y_train > 0]
            if len(y_train_filter) == 0: y_train_filter = y_train
            Q1 = float(np.percentile(y_train_filter, 25))
            Q3 = float(np.percentile(y_train_filter, 75))
            if Q1 == 0: Q1 = 1.0
            
            def get_status(pred):
                if pred < Q1: return "Rendah"
                elif pred > Q3: return "Tinggi"
                else: return "Sedang"

            # TAHAP 7: KALENDER MASA DEPAN (MENYAMBUNG DATA TERAKHIR SECARA URUT)
            tanggal_terakhir_db = df_resampled.index[-1]
            
            if resolusi_waktu == 'W':
                # Otomatis 52 Minggu dimulai dari minggu berikutnya setelah data terakhir
                start_future = tanggal_terakhir_db + pd.Timedelta(weeks=1)
                future_dates = pd.date_range(start=start_future, periods=52, freq='W')
            else:
                # Opsi Harian: Tangkap rentang tanggal spesifik dari admin
                if not start_date_pred or not end_date_pred:
                    conn.close()
                    flash("Untuk resolusi Harian, silakan isi Target Tanggal Awal dan Akhir!")
                    return redirect(url_for('analisis'))
                    
                target_start = pd.to_datetime(start_date_pred)
                target_end = pd.to_datetime(end_date_pred)
                
                if target_start > target_end:
                    conn.close()
                    flash("Target Tanggal Awal tidak boleh melewati Tanggal Akhir!")
                    return redirect(url_for('analisis'))

                all_days = pd.date_range(start=target_start, end=target_end, freq='D')
                num_days = len(all_days)
                
                # Hitung proporsi 4 hari operasi dalam seminggu
                active_days = int(num_days * (4/7))
                if active_days == 0: active_days = num_days
                
                np.random.seed(42) 
                chosen_indices = np.random.choice(num_days, size=active_days, replace=False)
                chosen_indices.sort() 
                future_dates = all_days[chosen_indices]
            
            # PENYIAPAN ATRIBUT UNTUK PREDIKSI (Harga, Stok, Hari)
            df_aktif_harga = train_df[train_df['harga'] > 0]
            avg_h = df_aktif_harga['harga'].mean() if not df_aktif_harga.empty else 5000.0
            df_aktif_stok = train_df[train_df['stok'] > 0]
            avg_s = df_aktif_stok['stok'].mean() if not df_aktif_stok.empty else 50.0

            np.random.seed(42)
            future_stok_random = np.random.normal(avg_s, avg_s * 0.1, len(future_dates))
            
            if resolusi_waktu == 'W':
                future_wknd = np.full(len(future_dates), 2)
                future_wkday = np.full(len(future_dates), 5)
            else:
                future_wknd = future_dates.dayofweek.map(lambda x: 1 if x >= 5 else 0).values
                future_wkday = future_dates.dayofweek.map(lambda x: 1 if x < 5 else 0).values

            X_future = np.column_stack([np.full(len(future_dates), avg_h), future_stok_random, np.zeros(len(future_dates)), future_wknd, future_wkday])
            
            F_future = np.full(len(future_dates), f0)
            for tree in models:
                F_future += learning_rate * tree.predict(X_future)
            F_future = np.round(F_future).astype(int)

            # TAHAP 8: MENYUSUN DATA & VISUALISASI MURNI
            hasil_prediksi = []
            for i in range(len(test_df)):
                aktual_val = int(y_test_aktual[i])
                pred_val = int(F_test_pred[i])
                if resolusi_waktu == 'D' and aktual_val == 0: continue
                hasil_prediksi.append({'periode': f"Validasi: {test_df.index[i].strftime('%d %b %Y')}", 'aktual': aktual_val, 'prediksi': pred_val, 'error': int(abs(aktual_val - pred_val)), 'status': get_status(pred_val)})

            for i in range(len(future_dates)):
                pred_val = int(F_future[i])
                if resolusi_waktu == 'D' and pred_val <= 0: continue
                hasil_prediksi.append({'periode': f"Proyeksi: {future_dates[i].strftime('%d %b %Y')}", 'aktual': "-", 'prediksi': pred_val, 'error': "-", 'status': get_status(pred_val)})

            plt.figure(figsize=(10, 4))
            plt.plot(test_df.index, y_test_aktual, label='Aktual Validasi', color='#000000', linestyle='-', marker='o')
            plt.plot(test_df.index, F_test_pred, label='Prediksi Model', color='#3498db', linestyle='--')
            
            # Memanggil langsung future_dates tanpa jembatan buatan
            plt.plot(future_dates, F_future, label='Ramalan Target', color='#e74c3c', linestyle='-.')
            
            plt.title(f'Validasi Historis & Target Peramalan: {jenis_roti}')
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.6)
            plt.tight_layout()
            img_trend = io.BytesIO()
            plt.savefig(img_trend, format='png', transparent=True); img_trend.seek(0)
            plot_trend_url = base64.b64encode(img_trend.getvalue()).decode('utf8'); plt.close()

            plt.figure(figsize=(6, 4))
            feat_labels = [f['fitur'] for f in feature_importance_list]
            feat_scores = [f['score'] for f in feature_importance_list]
            traffic_palette = ['#2ecc71', '#27ae60', '#f1c40f', '#f39c12', '#e74c3c']
            sns.barplot(x=feat_scores, y=feat_labels, hue=feat_labels, palette=traffic_palette[:len(feat_labels)], legend=False)
            plt.title('Faktor Dominan')
            plt.grid(axis='x', linestyle='--', alpha=0.7)
            plt.tight_layout()
            img_imp = io.BytesIO()
            plt.savefig(img_imp, format='png', transparent=True); img_imp.seek(0)
            plot_url = base64.b64encode(img_imp.getvalue()).decode('utf8'); plt.close()

            session['last_hasil'] = hasil_prediksi 
            session['last_mae'] = mae_manual
            session['last_plot'] = plot_trend_url
            session.modified = True 

            conn.close()
            return render_template('analisis.html', roti_list=roti_list, hasil=hasil_prediksi, mae=mae_manual, detail_mae=detail_mae, importance=feature_importance_list, plot_url=plot_url, plot_trend_url=plot_trend_url, q1=Q1, q3=Q3, roti_pilihan=jenis_roti, log_perhitungan=log_perhitungan)

        conn.close()
        return render_template('analisis.html', roti_list=roti_list)