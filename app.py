import streamlit as st
import pandas as pd
from collections import defaultdict
from io import BytesIO


def parse_excel(uploaded_file):
    excel_file = pd.ExcelFile(uploaded_file)
    sheet_names = excel_file.sheet_names

    if len(sheet_names) > 1:
        st.warning(f"'{uploaded_file.name}' has multiple sheets. Using the first one by default: '{sheet_names[0]}'")
        chosen_sheet = st.text_input(f"Optional: Enter sheet name to use for '{uploaded_file.name}'", value=sheet_names[0])
    else:
        chosen_sheet = sheet_names[0]

    try:
        return excel_file.parse(chosen_sheet)
    except Exception as e:
        st.error(f"Error reading sheet '{chosen_sheet}': {e}")
        return pd.DataFrame()  # Return empty DataFrame on failure


def preprocess_data(df):
    processed_rows = []
    for _, row in df.iterrows():
        owned_by = str(row['owned_by'])
        if owned_by != 'All' and ',' in owned_by:
            owners = [x.strip() for x in owned_by.split(',')]
            share = row['total_price'] / len(owners)
            for owner in owners:
                new_row = row.copy()
                new_row['owned_by'] = owner
                new_row['total_price'] = share
                processed_rows.append(new_row)
        else:
            processed_rows.append(row)
    return pd.DataFrame(processed_rows)


def get_unique_people(df, user_input_names):
    unique_people = {val.strip() for val in df['owned_by'] if val != 'All'}.union(df['paid_by'].unique())
    if user_input_names:
        unique_people.update({x.strip() for x in user_input_names.split(',') if x.strip()})
    return sorted(unique_people)


def calculate_debts(df, unique_people):
    df['owners_list'] = df['owned_by'].apply(lambda x: unique_people if x == 'All' else [x.strip()])
    paid_amounts = df.groupby('paid_by')['total_price'].sum()
    main_payer = paid_amounts.idxmax()

    st.subheader("💳 Total Bills Paid by Each Person")
    for name, amount in paid_amounts.items():
        st.write(f"{name}: {int(amount):,}")

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

    return net_debts, main_payer


def generate_result_df(net_debts, main_payer):
    result = [
        {'From': debtor, 'Paid to': main_payer, 'Paid amount': f"{round(amount, 2):,.2f}"}
        for debtor, amount in net_debts.items()
        if debtor != main_payer and amount > 0.01
    ]
    return pd.DataFrame(result).sort_values(by=['Paid to', 'From']).reset_index(drop=True)


def main():
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
            df = parse_excel(uploaded_file)
            if not df.empty:
                all_data.append(preprocess_data(df))

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            unique_people = get_unique_people(combined_df, user_input_names)
            net_debts, main_payer = calculate_debts(combined_df, unique_people)
            result_df = generate_result_df(net_debts, main_payer)

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


if __name__ == "__main__":
    main()