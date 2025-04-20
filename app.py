import streamlit as st
import pandas as pd
from collections import defaultdict
from io import BytesIO

st.title("Simplified Split Bill")
st.write("Upload Excel files with columns: item, merchant, price, quantity, total_price, owned_by, paid_by")
st.write("Notes for owned_by:")
st.write("1. If 'All' then total_price will be distributed equally across all unique person.")
st.write("2. In case of multiple, use comma (,) as separators.")
st.write("3. Add names manually if it hasn't appeared on the bill once.")

uploaded_files = st.file_uploader("Upload Excel Files", type=["xlsx"], accept_multiple_files=True)
user_input_names = st.text_input("Optional: Add unique names manually (separate by comma)")

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        df = pd.read_excel(uploaded_file)
        for _, row in df.iterrows():
            owned_by = str(row['owned_by'])
            if owned_by != 'All' and ',' in owned_by:
                owners = [x.strip() for x in owned_by.split(',')]
                share = row['total_price'] / len(owners)
                for owner in owners:
                    new_row = row.copy()
                    new_row['owned_by'] = owner
                    new_row['total_price'] = share
                    all_data.append(new_row)
            else:
                all_data.append(row)

    df = pd.DataFrame(all_data)

    unique_people = {val.strip() for val in df['owned_by'] if val != 'All'}.union(df['paid_by'].unique())
    if user_input_names:
        unique_people.update({x.strip() for x in user_input_names.split(',') if x.strip()})
    unique_people = sorted(unique_people)

    df['owners_list'] = df['owned_by'].apply(lambda x: unique_people if x == 'All' else [x.strip()])

    paid_amounts = df.groupby('paid_by')['total_price'].sum()
    main_payer = paid_amounts.idxmax()

    # 💳 Section: Total Bills Paid by Each Person
    st.subheader("💳 Total Bills Paid by Each Person")
    for name, amount in paid_amounts.items():
        st.write(f"{name} – {int(amount):,}")

    debts = defaultdict(lambda: defaultdict(float))
    for _, row in df.iterrows():
        share = row['total_price'] / len(row['owners_list'])
        for owner in row['owners_list']:
            if owner != row['paid_by']:
                debts[owner][row['paid_by']] += share

    net_debts = defaultdict(float)
    for debtor, creditor_dict in debts.items():
        for creditor, amount in creditor_dict.items():
            if creditor == main_payer:
                net_debts[debtor] += amount
            else:
                net_debts[debtor] += amount
                net_debts[creditor] -= amount

    result_df = pd.DataFrame([
        {'From': debtor, 'Paid to': main_payer, 'Paid amount': round(amount, 2)}
        for debtor, amount in net_debts.items()
        if debtor != main_payer and amount > 0.01
    ]).sort_values(by=['Paid to', 'From', 'Paid amount']).reset_index(drop=True)

    st.subheader("💰 Final Redistributed Bill")
    st.dataframe(result_df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, index=False)
    output.seek(0)

    st.download_button(
        label="Download Result as Excel",
        data=output,
        file_name="simplified_split_bill.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
