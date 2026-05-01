import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import re

st.set_page_config(page_title="TG-DTA Data Analyzer", layout="wide")

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        # ↓↓↓ ここが合言葉（パスワード）です。好きな文字に変更できます ↓↓↓
        if st.session_state["password"] == "tgdta2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # セキュリティのためパスワードを削除
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 初回アクセス時
        st.markdown("### 🔒 アプリを利用するにはパスワードが必要です")
        st.text_input(
            "合言葉を入力してEnterキーを押してください", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # パスワード間違い時
        st.markdown("### 🔒 アプリを利用するにはパスワードが必要です")
        st.text_input(
            "合言葉を入力してEnterキーを押してください", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 パスワードが間違っています。もう一度お試しください。")
        return False
    else:
        # パスワード正解
        return True

# パスワードが正解しない場合はここで処理をストップ（画面を見せない）
if not check_password():
    st.stop()

st.title("TG-DTA Data Analyzer")
st.markdown("TG-DTAのCSVデータをアップロードし、グラフの可視化とCa(OH)2、CaCO3、DoCの計算を行います。")

# Sidebar for inputs
st.sidebar.header("計算パラメータ設定")
st.sidebar.markdown("### DoC計算用パラメータ")
m_ch0_norm = st.sidebar.number_input("m_(CH0,norm) [%]", value=20.53, step=0.1)
m_ca0_cem = st.sidebar.number_input("m_(Ca0,cem) [%]", value=65.01, step=0.1)
m_950_cem = st.sidebar.number_input("m_(950,cem)", value=98.10, step=0.1)
dry_temp = st.sidebar.number_input("HCP質量基準温度 (℃)", value=105.0, step=1.0)

# File uploader
uploaded_files = st.file_uploader("TG-DTAデータ(CSV)をアップロードしてください（複数選択可）", type=['csv'], accept_multiple_files=True)

if uploaded_files:
    # グラフ用のFigureを作成
    fig_tg = go.Figure()
    fig_dtg = go.Figure()

    processed_data = []

    # 各ファイルを処理
    for uploaded_file in uploaded_files:
        content = uploaded_file.getvalue().decode('utf-8', errors='replace')
        lines = content.split('\n')
        
        header_idx = 0
        sample_mass = 15.0 # default
        for i, line in enumerate(lines):
            if 'SAMPLE MASS' in line.upper():
                parts = line.split(',')
                for p in parts[1:]:
                    if p.strip():
                        try:
                            sample_mass = float(p.strip())
                            break
                        except:
                            pass
            if line.startswith('##Temp.'):
                header_idx = i
                break
                
        # Load data
        df = pd.read_csv(io.StringIO(content), skiprows=header_idx, encoding='utf-8', on_bad_lines='skip')
        
        temp_col = df.columns[0]
        time_col = df.columns[1]
        dta_col = df.columns[2]
        tg_col = df.columns[3] # Mass loss/mg
        dtg_col = df.columns[6] # DTG/(mg/min)
        
        # Add traces to figures
        fig_tg.add_trace(go.Scatter(x=df[temp_col], y=df[tg_col], name=uploaded_file.name))
        fig_dtg.add_trace(go.Scatter(x=df[temp_col], y=df[dtg_col], name=uploaded_file.name))

        processed_data.append({
            'name': uploaded_file.name,
            'df': df,
            'sample_mass': sample_mass,
            'temp_col': temp_col,
            'time_col': time_col,
            'dta_col': dta_col,
            'tg_col': tg_col,
            'dtg_col': dtg_col
        })

    # Mass Loss Graph
    fig_tg.update_layout(
        title_text="TG (Mass loss) Curves", 
        xaxis_title="Temperature (℃)", 
        yaxis_title="Mass loss (mg)",
        legend=dict(x=0.01, y=0.99, bordercolor="Black", borderwidth=1)
    )
    st.plotly_chart(fig_tg, use_container_width=True)

    # DTG Graph
    fig_dtg.update_layout(
        title_text="DTG Curves", 
        xaxis_title="Temperature (℃)", 
        yaxis_title="DTG (mg/min)",
        legend=dict(x=0.01, y=0.99, bordercolor="Black", borderwidth=1)
    )
    st.plotly_chart(fig_dtg, use_container_width=True)

    # Calculation Logic
    st.header("各ファイルの計算結果")
    
    def get_mass_loss(df, temp_col, time_col, dtg_col, t_min, t_max):
        df_filtered = df[(df[temp_col] >= t_min) & (df[temp_col] <= t_max)]
        if len(df_filtered) > 1:
            dtg_start = df_filtered[dtg_col].iloc[0]
            dtg_end = df_filtered[dtg_col].iloc[-1]
            t = df_filtered[time_col].values
            dtg = df_filtered[dtg_col].values
            
            baseline = np.interp(t, [t[0], t[-1]], [dtg_start, dtg_end])
            
            try:
                area = np.trapezoid(dtg - baseline, t)
            except AttributeError:
                area = np.trapz(dtg - baseline, t)
                
            return abs(area)
        return 0.0

    if processed_data:
        tabs = st.tabs([d['name'] for d in processed_data])
        
        for i, data in enumerate(processed_data):
            with tabs[i]:
                df = data['df']
                temp_col = data['temp_col']
                time_col = data['time_col']
                tg_col = data['tg_col']
                dtg_col = data['dtg_col']
                sample_mass = data['sample_mass']

                st.subheader("データごとの設定")
                st.markdown("**温度範囲の設定 (直接入力、または右端の＋－ボタンで調整)**")
                col_p1, col_p2, col_p3 = st.columns(3)
                with col_p1:
                    point1 = st.number_input("ポイント1 (Ca(OH)2 下限)", min_value=100.0, max_value=1000.0, value=403.0, step=1.0, key=f"p1_{i}")
                with col_p2:
                    point2 = st.number_input("ポイント2 (Ca(OH)2上限/CaCO3下限)", min_value=100.0, max_value=1000.0, value=517.0, step=1.0, key=f"p2_{i}")
                with col_p3:
                    point3 = st.number_input("ポイント3 (CaCO3 上限)", min_value=100.0, max_value=1000.0, value=735.0, step=1.0, key=f"p3_{i}")
                
                ch_temp_range = (point1, point2)
                cc_temp_range = (point2, point3)

                fig_single_dtg = go.Figure()
                fig_single_dtg.add_trace(go.Scatter(x=df[temp_col], y=df[dtg_col], name=data['name']))
                fig_single_dtg.add_vrect(x0=ch_temp_range[0], x1=ch_temp_range[1], 
                              fillcolor="LightSalmon", opacity=0.3, layer="below", line_width=0)
                fig_single_dtg.add_vrect(x0=cc_temp_range[0], x1=cc_temp_range[1], 
                              fillcolor="LightGreen", opacity=0.3, layer="below", line_width=0)
                fig_single_dtg.update_layout(
                    title="個別DTG曲線と積分範囲", 
                    xaxis_title="Temperature (℃)", 
                    yaxis_title="DTG (mg/min)",
                    height=350, margin=dict(t=40, b=10, l=10, r=10)
                )
                st.plotly_chart(fig_single_dtg, use_container_width=True)

                st.subheader("アップロードされたデータ")
                st.dataframe(df.head())

                mass_loss_ch = get_mass_loss(df, temp_col, time_col, dtg_col, ch_temp_range[0], ch_temp_range[1])
                mass_loss_cc = get_mass_loss(df, temp_col, time_col, dtg_col, cc_temp_range[0], cc_temp_range[1])
                
                # 基準となるHCP質量 (dry_tempでの質量) を取得
                df_valid = df.dropna(subset=[temp_col, tg_col])
                if len(df_valid) > 0:
                    idx_dry = (df_valid[temp_col] - dry_temp).abs().idxmin()
                    m_hcp_mg = sample_mass + df_valid.loc[idx_dry, tg_col]
                    
                    idx_950 = (df_valid[temp_col] - 950.0).abs().idxmin()
                    m_950_abs_mg = sample_mass + df_valid.loc[idx_950, tg_col]
                else:
                    m_hcp_mg = sample_mass
                    m_950_abs_mg = sample_mass

                # 絶対質量 (mg)
                caoh2_mg = mass_loss_ch * (74.09 / 18.02)
                caco3_mg = mass_loss_cc * (100.09 / 44.01)

                # HCP100gあたりの質量 (mCH, mCC, m950)
                m_ch = (caoh2_mg / m_hcp_mg) * 100 if m_hcp_mg != 0 else 0.0
                m_cc = (caco3_mg / m_hcp_mg) * 100 if m_hcp_mg != 0 else 0.0
                m_950 = (m_950_abs_mg / m_hcp_mg) * 100 if m_hcp_mg != 0 else 0.0

                # セメント100gあたりの質量 (m_CH_norm, m_CC_norm)
                m_ch_norm = (m_ch / m_950) * m_950_cem if m_950 != 0 else 0.0
                m_cc_norm = (m_cc / m_950) * m_950_cem if m_950 != 0 else 0.0

                # DoC Formulas
                doc_ch = ((m_ch0_norm - m_ch_norm) / m_ch0_norm) * 100 if m_ch0_norm != 0 else 0.0
                doc_hcp = ((m_cc_norm * (56.0 / 100.0)) / m_ca0_cem) * 100 if m_ca0_cem != 0 else 0.0

                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("成分量の計算")
                    st.write(f"**HCP基準質量 ({dry_temp}℃)**: {m_hcp_mg:.4f} mg")
                    st.write(f"**m_950** (強熱質量 / HCP100g): {m_950:.4f}")
                    st.write("---")
                    st.write(f"**Ca(OH)2 質量**: {caoh2_mg:.4f} mg (H2O減少量[ベースライン補正済]: {mass_loss_ch:.4f} mg)")
                    st.write(f"**m_CH** (HCP100gあたり): `{caoh2_mg:.4f}/{m_hcp_mg:.4f} × 100` = **{m_ch:.4f}**")
                    st.write(f"**m_(CH,norm)**: `{m_ch:.4f} / {m_950:.4f} × {m_950_cem}` = **{m_ch_norm:.4f}**")
                    st.write("---")
                    st.write(f"**CaCO3 質量**: {caco3_mg:.4f} mg (CO2減少量[ベースライン補正済]: {mass_loss_cc:.4f} mg)")
                    st.write(f"**m_CC** (HCP100gあたり): `{caco3_mg:.4f}/{m_hcp_mg:.4f} × 100` = **{m_cc:.4f}**")
                    st.write(f"**m_(CC,norm)**: `{m_cc:.4f} / {m_950:.4f} × {m_950_cem}` = **{m_cc_norm:.4f}**")

                with col2:
                    st.subheader("DoC (炭酸化度) の計算")
                    st.write("**DoC_CH (%)**")
                    st.latex(r"\frac{m_{CH0,norm} - m_{CH,norm}}{m_{CH0,norm}} \times 100")
                    st.write(f" `= ({m_ch0_norm} - {m_ch_norm:.4f}) / {m_ch0_norm} × 100`")
                    st.write(f"**= {doc_ch:.2f} %**")
                    
                    st.write("---")
                    st.write("**DoC_HCP (%)**")
                    st.latex(r"\frac{m_{CC,norm} \times \frac{56}{100}}{m_{Ca0,cem}} \times 100")
                    st.write(f" `= ({m_cc_norm:.4f} × 56 / 100) / {m_ca0_cem} × 100`")
                    st.write(f"**= {doc_hcp:.2f} %**")
