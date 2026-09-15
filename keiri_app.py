import os
import pandas as pd
import streamlit as st
from datetime import date

# =========================================================
# 1. 設定・定数
# =========================================================

# 仕訳データを保存する CSV ファイルのパス
DATA_FILE = "journal_entries.csv"

# 仕訳データの列（カラム）定義
COLUMNS = ["日付", "借方科目", "借方金額", "貸方科目", "貸方金額", "摘要"]

# 勘定科目マスタ：科目名 → 区分（資産／負債／純資産／収益／費用）
# 必要に応じて自由に科目を追加・変更してよい
ACCOUNT_MASTER = {
    # 資産
    "現金": "資産",
    "普通預金": "資産",
    "売掛金": "資産",
    "商品": "資産",
    "建物": "資産",
    "備品": "資産",
    # 負債
    "買掛金": "負債",
    "借入金": "負債",
    "未払金": "負債",
    # 純資産
    "資本金": "純資産",
    "繰越利益剰余金": "純資産",
    # 収益
    "売上高": "収益",
    "受取利息": "収益",
    "雑収入": "収益",
    # 費用
    "仕入高": "費用",
    "給料": "費用",
    "家賃": "費用",
    "水道光熱費": "費用",
    "通信費": "費用",
    "消耗品費": "費用",
    "支払利息": "費用",
    "雑費": "費用",
}

ACCOUNT_LIST = list(ACCOUNT_MASTER.keys())

# 借方側で残高が増える区分／貸方側で残高が増える区分
DEBIT_INCREASE_TYPES = {"資産", "費用"}
CREDIT_INCREASE_TYPES = {"負債", "純資産", "収益"}


# =========================================================
# 2. データの読み込み・保存（os を使ってファイルの有無を確認）
# =========================================================

def load_journal() -> pd.DataFrame:
    """CSVファイルから仕訳データを読み込む。ファイルが無ければ空のデータを作る"""
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # 日付列を日付型として扱えるように変換しておく
        df["日付"] = pd.to_datetime(df["日付"]).dt.date
        return df
    else:
        # 空のデータフレーム（列だけ用意）を返す
        return pd.DataFrame(columns=COLUMNS)


def save_journal(df: pd.DataFrame) -> None:
    """仕訳データをCSVファイルに保存する"""
    df.to_csv(DATA_FILE, index=False)


# セッション内で使い回すために、初回だけファイルから読み込む
if "journal_df" not in st.session_state:
    st.session_state.journal_df = load_journal()


# =========================================================
# 3. 集計ロジック
# =========================================================

def calc_account_balances(df: pd.DataFrame) -> pd.DataFrame:
    """勘定科目ごとに、借方合計・貸方合計・残高を計算する（試算表のもと）"""
    if df.empty:
        return pd.DataFrame(columns=["科目", "区分", "借方合計", "貸方合計", "残高"])

    # 借方側の金額を科目ごとに合計
    debit_sum = df.groupby("借方科目")["借方金額"].sum()
    # 貸方側の金額を科目ごとに合計
    credit_sum = df.groupby("貸方科目")["貸方金額"].sum()

    rows = []
    for account in ACCOUNT_LIST:
        d = float(debit_sum.get(account, 0))
        c = float(credit_sum.get(account, 0))
        account_type = ACCOUNT_MASTER[account]

        # 区分によって、借方が増えるか貸方が増えるかで残高の計算方法が違う
        if account_type in DEBIT_INCREASE_TYPES:
            balance = d - c
        else:
            balance = c - d

        # 一度も使われていない科目は一覧から省く
        if d == 0 and c == 0:
            continue

        rows.append(
            {"科目": account, "区分": account_type, "借方合計": d, "貸方合計": c, "残高": balance}
        )

    return pd.DataFrame(rows)


def calc_profit_and_loss(balance_df: pd.DataFrame):
    """損益計算書用に、収益・費用の内訳と当期純利益を計算する"""
    revenue_df = balance_df[balance_df["区分"] == "収益"]
    expense_df = balance_df[balance_df["区分"] == "費用"]

    total_revenue = revenue_df["残高"].sum()
    total_expense = expense_df["残高"].sum()
    net_income = total_revenue - total_expense  # 当期純利益（マイナスなら当期純損失）

    return revenue_df, expense_df, total_revenue, total_expense, net_income


def calc_balance_sheet(balance_df: pd.DataFrame, net_income: float):
    """貸借対照表用に、資産・負債・純資産の内訳を計算する"""
    asset_df = balance_df[balance_df["区分"] == "資産"]
    liability_df = balance_df[balance_df["区分"] == "負債"]
    equity_df = balance_df[balance_df["区分"] == "純資産"]

    total_asset = asset_df["残高"].sum()
    total_liability = liability_df["残高"].sum()
    total_equity = equity_df["残高"].sum()

    # 損益計算書で出た当期純利益は、貸借対照表では純資産の増加分として扱う
    total_equity_with_income = total_equity + net_income

    total_liability_and_equity = total_liability + total_equity_with_income

    return (
        asset_df,
        liability_df,
        equity_df,
        total_asset,
        total_liability,
        total_equity_with_income,
        total_liability_and_equity,
    )


# =========================================================
# 4. 画面（Streamlit UI）
# =========================================================

st.set_page_config(page_title="簡易会計システム", layout="wide")
st.title("📒 簡易会計システム")

# サイドバーで画面（機能）を切り替える
menu = st.sidebar.radio(
    "メニュー",
    ["仕訳入力", "仕訳一覧", "勘定科目集計（試算表）", "損益計算書", "貸借対照表"],
)

# ---------------------------------------------------------
# 4-1. 仕訳入力画面
# ---------------------------------------------------------
if menu == "仕訳入力":
    st.header("✏️ 仕訳入力")
    st.write("1つの取引を「借方」と「貸方」に分けて入力してください。借方金額と貸方金額は必ず一致させます。")

    with st.form("journal_entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            entry_date = st.date_input("日付", value=date.today())
            debit_account = st.selectbox("借方科目", ACCOUNT_LIST, key="debit_account")
            debit_amount = st.number_input("借方金額", min_value=0, step=1)

        with col2:
            description = st.text_input("摘要（取引の内容メモ）")
            credit_account = st.selectbox("貸方科目", ACCOUNT_LIST, key="credit_account")
            credit_amount = st.number_input("貸方金額", min_value=0, step=1)

        submitted = st.form_submit_button("仕訳を登録する")

        if submitted:
            # 金額が0、または借方・貸方の金額が一致しない場合はエラーにする
            if debit_amount <= 0 or credit_amount <= 0:
                st.error("借方金額・貸方金額は0より大きい値を入力してください。")
            elif debit_amount != credit_amount:
                st.error(
                    f"借方金額（{debit_amount:,}）と貸方金額（{credit_amount:,}）が一致していません。"
                )
            else:
                # 新しい仕訳を1行のデータフレームとして作成
                new_row = pd.DataFrame(
                    [
                        {
                            "日付": entry_date,
                            "借方科目": debit_account,
                            "借方金額": debit_amount,
                            "貸方科目": credit_account,
                            "貸方金額": credit_amount,
                            "摘要": description,
                        }
                    ]
                )
                # 既存データに追加して、セッションとCSVの両方を更新
                st.session_state.journal_df = pd.concat(
                    [st.session_state.journal_df, new_row], ignore_index=True
                )
                save_journal(st.session_state.journal_df)
                st.success("仕訳を登録しました。")

# ---------------------------------------------------------
# 4-2. 仕訳一覧画面
# ---------------------------------------------------------
elif menu == "仕訳一覧":
    st.header("📋 仕訳一覧")

    df = st.session_state.journal_df

    if df.empty:
        st.info("まだ仕訳が登録されていません。「仕訳入力」画面から登録してください。")
    else:
        # 日付順に並び替えて表示
        display_df = df.sort_values("日付").reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True)

        st.write(f"件数：{len(display_df)} 件")
        st.write(f"借方合計：{display_df['借方金額'].sum():,.0f} 円")
        st.write(f"貸方合計：{display_df['貸方金額'].sum():,.0f} 円")

        # ---- 仕訳一覧をCSVファイルとしてダウンロードできるようにする ----
        # DataFrame をCSV形式の文字列（バイト列）に変換する
        # encoding="utf-8-sig" にすると、Excelで開いたときに文字化けしにくい
        csv_data = display_df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="⬇️ 仕訳一覧をCSVでダウンロード",
            data=csv_data,
            file_name=f"仕訳一覧_{date.today()}.csv",
            mime="text/csv",
        )

        # 特定の行を削除できるようにする（間違えて入力した場合の修正用）
        st.subheader("仕訳の削除")
        row_to_delete = st.number_input(
            "削除したい行番号（上の表の一番左の番号）を入力してください",
            min_value=0,
            max_value=max(len(display_df) - 1, 0),
            step=1,
        )
        if st.button("この行を削除する"):
            display_df = display_df.drop(index=row_to_delete).reset_index(drop=True)
            st.session_state.journal_df = display_df
            save_journal(display_df)
            st.success("削除しました。画面を再読み込みします。")
            st.rerun()

# ---------------------------------------------------------
# 4-3. 勘定科目集計（試算表）画面
# ---------------------------------------------------------
elif menu == "勘定科目集計（試算表）":
    st.header("📊 勘定科目集計（試算表）")

    balance_df = calc_account_balances(st.session_state.journal_df)

    if balance_df.empty:
        st.info("まだ仕訳が登録されていません。")
    else:
        # 区分ごとにグループ分けして見やすく表示
        for account_type in ["資産", "負債", "純資産", "収益", "費用"]:
            sub_df = balance_df[balance_df["区分"] == account_type]
            if not sub_df.empty:
                st.subheader(account_type)
                st.dataframe(
                    sub_df[["科目", "借方合計", "貸方合計", "残高"]].reset_index(drop=True),
                    use_container_width=True,
                )

# ---------------------------------------------------------
# 4-4. 損益計算書画面
# ---------------------------------------------------------
elif menu == "損益計算書":
    st.header("💰 損益計算書（P/L）")

    balance_df = calc_account_balances(st.session_state.journal_df)

    if balance_df.empty:
        st.info("まだ仕訳が登録されていません。")
    else:
        revenue_df, expense_df, total_revenue, total_expense, net_income = calc_profit_and_loss(
            balance_df
        )

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("収益")
            st.dataframe(revenue_df[["科目", "残高"]].reset_index(drop=True), use_container_width=True)
            st.write(f"**収益合計：{total_revenue:,.0f} 円**")

        with col2:
            st.subheader("費用")
            st.dataframe(expense_df[["科目", "残高"]].reset_index(drop=True), use_container_width=True)
            st.write(f"**費用合計：{total_expense:,.0f} 円**")

        st.divider()
        if net_income >= 0:
            st.success(f"当期純利益：{net_income:,.0f} 円")
        else:
            st.error(f"当期純損失：{abs(net_income):,.0f} 円")

# ---------------------------------------------------------
# 4-5. 貸借対照表画面
# ---------------------------------------------------------
elif menu == "貸借対照表":
    st.header("🏦 貸借対照表（B/S）")

    balance_df = calc_account_balances(st.session_state.journal_df)

    if balance_df.empty:
        st.info("まだ仕訳が登録されていません。")
    else:
        # 貸借対照表を作るには、まず損益計算書の当期純利益を求める必要がある
        _, _, _, _, net_income = calc_profit_and_loss(balance_df)

        (
            asset_df,
            liability_df,
            equity_df,
            total_asset,
            total_liability,
            total_equity_with_income,
            total_liability_and_equity,
        ) = calc_balance_sheet(balance_df, net_income)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("資産の部")
            st.dataframe(asset_df[["科目", "残高"]].reset_index(drop=True), use_container_width=True)
            st.write(f"**資産合計：{total_asset:,.0f} 円**")

        with col2:
            st.subheader("負債の部")
            st.dataframe(liability_df[["科目", "残高"]].reset_index(drop=True), use_container_width=True)
            st.write(f"負債合計：{total_liability:,.0f} 円")

            st.subheader("純資産の部")
            st.dataframe(equity_df[["科目", "残高"]].reset_index(drop=True), use_container_width=True)
            st.write(f"当期純利益（損益計算書より）：{net_income:,.0f} 円")
            st.write(f"**純資産合計：{total_equity_with_income:,.0f} 円**")

        st.divider()
        st.write(f"**負債・純資産合計：{total_liability_and_equity:,.0f} 円**")

        # 資産合計と負債・純資産合計が一致しているかをチェック（複式簿記の検算）
        if abs(total_asset - total_liability_and_equity) < 0.01:
            st.success("✅ 資産合計 と 負債・純資産合計 が一致しています（貸借バランスOK）")
        else:
            st.warning(
                "⚠️ 資産合計 と 負債・純資産合計 が一致していません。仕訳の入力内容を確認してください。"
            )
