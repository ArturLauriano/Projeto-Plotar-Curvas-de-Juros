import requests
import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np
from scipy.interpolate import CubicSpline
import tkinter as tk
from tkinter import simpledialog
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import sys

# URL do arquivo CSV
url = 'https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv'
# Determinar o caminho do executável dinamicamente
if getattr(sys, 'frozen', False):
    # O script está sendo executado como um executável
    local_path = os.path.join(sys._MEIPASS, 'PrecoTaxaTesouroDireto.csv')
else:
    # O script está sendo executado como um script normal
    local_path = os.path.join(os.path.dirname(__file__), 'PrecoTaxaTesouroDireto.csv')

def download_csv(url, local_path):
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        response = requests.get(url)
        if response.status_code == 200:
            with open(local_path, 'wb') as file:
                file.write(response.content)
            print("Arquivo encontrado e baixado com sucesso, substituindo o antigo.")
        else:
            print("Não foi possível baixar o arquivo. Usando o arquivo local.")
    except Exception as e:
        print(f"Erro ao tentar baixar o arquivo: {e}. Usando o arquivo local.")

def rename_titles(df):
    def rename(row):
        title = row['Tipo Titulo']
        year = row['Data Vencimento'][-4:]
        if 'Tesouro IPCA+ com Juros Semestrais' in title:
            return f'NTN-B {year}'
        elif 'Tesouro IPCA+' in title:
            return f'NTN-B Principal {year}'
        elif 'Tesouro Prefixado com Juros Semestrais' in title:
            return f'NTN-F {year}'
        elif 'Tesouro Prefixado' in title:
            return f'LTN {year}'
        else:
            return title
    df['Tipo Titulo'] = df.apply(rename, axis=1)
    return df

def process_data(file_path):
    try:
        df = pd.read_csv(file_path, sep=';', encoding='latin1')
        print("Dados carregados com sucesso.")
        
        df = rename_titles(df)
        df['Taxa Compra Manha'] = pd.to_numeric(df['Taxa Compra Manha'].str.replace(',', '.'), errors='coerce')
        df['Taxa Venda Manha'] = pd.to_numeric(df['Taxa Venda Manha'].str.replace(',', '.'), errors='coerce')
        df['Taxa Indicativa'] = ((df['Taxa Compra Manha'] + df['Taxa Venda Manha']) / 2).round(2)
        today = datetime.now()
        
        root = tk.Tk()
        root.state('zoomed')
        root.configure(bg='black')
        root.title("Curvas de Taxas Indicativas")

        def on_closing():
            root.destroy()
            exit()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        main_frame = tk.Frame(root, bg='black')
        main_frame.pack(fill=tk.BOTH, expand=1)

        left_frame = tk.Frame(main_frame, bg='black')
        left_frame.pack(side=tk.LEFT, fill=tk.Y)

        right_frame = tk.Frame(main_frame, bg='black')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)

        control_frame = tk.Frame(left_frame, bg='black')
        control_frame.pack(fill=tk.X)
        
        tk.Label(control_frame, text="Selecione o tipo de curva:", bg='black', fg='white').grid(row=0, column=0, padx=10, pady=10)
        curve_type_var = tk.StringVar(value="Prefixada")
        ttk.Combobox(control_frame, textvariable=curve_type_var, values=["IPCA+", "Prefixada", "Inflação Implícita"]).grid(row=0, column=1, padx=10, pady=10)

        tk.Label(control_frame, text="Quantidade de curvas:", bg='black', fg='white').grid(row=1, column=0, padx=10, pady=10)
        num_curves_var = tk.StringVar(value="1")
        ttk.Combobox(control_frame, textvariable=num_curves_var, values=[str(i) for i in range(1, 6)]).grid(row=1, column=1, padx=10, pady=10)

        date_type_var = []
        custom_dates = []

        for i in range(5):
            tk.Label(control_frame, text=f"Tipo de data para a curva {i+1}:", bg='black', fg='white').grid(row=2+i, column=0, padx=10, pady=10)
            var = tk.StringVar(value="Hoje")
            date_type_var.append(var)
            combobox = ttk.Combobox(control_frame, textvariable=var, values=["Hoje", "1 Semana", "1 Mês", "1 Ano", "Outra"])
            combobox.grid(row=2+i, column=1, padx=10, pady=10)
            custom_dates.append(None)

            def on_combobox_change(event, index=i):
                if event.widget.get() == "Outra":
                    custom_date = simpledialog.askstring("Input", f"Digite a data para a curva {index+1} (formato dia/mês/ano):", parent=root)
                    try:
                        date_obj = datetime.strptime(custom_date, '%d/%m/%Y')
                        custom_dates[index] = date_obj
                        date_type_var[index].set(custom_date)  # Atualiza a exibição do valor na combobox
                    except ValueError:
                        tk.messagebox.showerror("Erro", "Formato de data inválido. Tente novamente.")
                        custom_dates[index] = None
                else:
                    custom_dates[index] = None

            combobox.bind("<<ComboboxSelected>>", on_combobox_change)

        curve_points = []

        def update_plot():
            curve_points.clear()
            curve_type = curve_type_var.get()
            num_curves = int(num_curves_var.get())
            dates = [date_type_var[i].get() for i in range(num_curves)]

            ax1.clear()
            all_x, all_y, curves = [], [], []

            for i, date in enumerate(dates):
                if date == "Hoje":
                    date_obj = today
                elif date == "1 Semana":
                    date_obj = today - timedelta(weeks=1)
                elif date == "1 Mês":
                    date_obj = today - timedelta(days=30)
                elif date == "1 Ano":
                    date_obj = today - timedelta(days=365)
                else:
                    date_obj = custom_dates[i]
                    if date_obj is None:
                        continue
                
                df['Data Vencimento'] = pd.to_datetime(df['Data Vencimento'], format='%d/%m/%Y')
                df['Data Base'] = pd.to_datetime(df['Data Base'], format='%d/%m/%Y')
                closest_date = df.loc[(df['Data Base'] - date_obj).abs().idxmin()]['Data Base']
                df_filtered = df[df['Data Base'] == closest_date].drop_duplicates(subset=['Data Vencimento']).sort_values(by='Data Vencimento')
                
                if curve_type in ["IPCA+", "Prefixada"]:
                    x, y, curve = plot_curve(ax1, df_filtered[df_filtered['Tipo Titulo'].str.contains('NTN-B' if curve_type == "IPCA+" else 'LTN|NTN-F')], date, curve_type)
                    all_x.append(x)
                    all_y.append(y)
                    curves.append(curve)
                    curve_points.append((df_filtered[df_filtered['Tipo Titulo'].str.contains('NTN-B' if curve_type == "IPCA+" else 'LTN|NTN-F')][['Data Vencimento', 'Taxa Indicativa']], date))
                
                if curve_type == "Inflação Implícita":
                    df_prefixada = df_filtered[df_filtered['Tipo Titulo'].str.contains('LTN|NTN-F')]
                    df_ipca = df_filtered[df_filtered['Tipo Titulo'].str.contains('NTN-B')]
                    
                    if not df_prefixada.empty and not df_ipca.empty:
                        df_inflacao_implicita = calculate_inflation_implicit(df_prefixada, df_ipca)
                        
                        if not df_inflacao_implicita.empty:
                            x_valid = df_inflacao_implicita['x']
                            y_valid = df_inflacao_implicita['y']
                            
                            ax1.plot(x_valid, y_valid, 'o', markersize=5)
                            cs = CubicSpline(x_valid, y_valid)
                            x_new = np.linspace(x_valid.min(), min(10, x_valid.max()), 500)
                            y_new = cs(x_new)
                            ax1.plot(x_new, y_new, linestyle='--', label=f'Inflação Implícita Interpolada - {date}')
                            curve_points.append((df_inflacao_implicita, date))
                        
            if all_x and all_y:
                max_x = min([x.max() for x in all_x if x.size > 0])
                min_y = min([y.min() for y in all_y if y.size > 0])
                max_y = max([y.max() for y in all_y if y.size > 0])
                
                ax1.set_xlim(0, max_x + 2)
                ax1.set_ylim(min_y - 0.5, max_y + 0.5)
            
            plt.title(f'Curvas de Taxas Indicativas - {curve_type}', color='white')
            ax1.set_xlabel('Anos até o Vencimento', color='white')
            ax1.set_ylabel('Taxa Indicativa (%)', color='white')
            ax1.tick_params(axis='x', colors='white')
            ax1.tick_params(axis='y', colors='white')
            ax1.spines['bottom'].set_color('white')
            ax1.spines['top'].set_color('white') 
            ax1.spines['right'].set_color('white')
            ax1.spines['left'].set_color('white')
            plt.grid(True, color='gray', linestyle='-', linewidth=0.5)
            plt.tight_layout()
            ax1.legend()
            canvas.draw()

        def show_data():
            data_window = tk.Toplevel(root)
            data_window.title("Dados das Curvas")
            data_window.configure(bg='black')

            data_frame = tk.Frame(data_window, bg='black')
            data_frame.pack(fill=tk.BOTH, expand=1)

            columns = ['Data Vencimento']
            for date_label in date_type_var[:int(num_curves_var.get())]:
                date_label_str = date_label.get()
                columns.append(f'Taxa - {date_label_str}')

            tree = ttk.Treeview(data_frame, columns=columns, show='headings', style='mystyle.Treeview')

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, anchor='center')

            # Inserir dados nas colunas apropriadas
            data_dict = {}
            for points, date_label in curve_points:
                date_label_str = date_label if isinstance(date_label, str) else date_label.strftime('%d/%m/%Y')
                for _, row in points.iterrows():
                    vencimento = row['Data Vencimento'].strftime('%d/%m/%Y')
                    taxa = row['Taxa Indicativa']
                    if vencimento not in data_dict:
                        data_dict[vencimento] = {}
                    data_dict[vencimento][f'Taxa - {date_label_str}'] = taxa

            for vencimento in sorted(data_dict.keys()):
                row_data = [vencimento]
                for col in columns[1:]:
                    row_data.append(data_dict[vencimento].get(col, ''))
                tree.insert("", "end", values=row_data)

            tree.pack(fill=tk.BOTH, expand=1)

            vsb = ttk.Scrollbar(data_frame, orient="vertical", command=tree.yview)
            vsb.pack(side=tk.RIGHT, fill='y')
            tree.configure(yscrollcommand=vsb.set)

            ttk.Style().configure("mystyle.Treeview", background="black", foreground="orange", fieldbackground="black", font=('Helvetica', 10))
            ttk.Style().map("mystyle.Treeview", background=[('selected', 'orange')])

        tk.Button(control_frame, text="Carregar", command=update_plot).grid(row=7, column=0, columnspan=2, padx=10, pady=10)
        tk.Button(control_frame, text="Mostrar Dados", command=show_data).grid(row=8, column=0, columnspan=2, padx=10, pady=10)

        fig, ax1 = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor('black')
        ax1.set_facecolor('black')
        canvas = FigureCanvasTkAgg(fig, master=right_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(canvas, right_frame)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        empty_space = tk.Frame(left_frame, bg='black')
        empty_space.pack(fill=tk.BOTH, expand=True)

        label_autor = tk.Label(left_frame, text="By: Artur Lauriano", bg='black', fg='white', anchor='w')
        label_autor.pack(side=tk.LEFT, padx=10, pady=10)
        label_fonte = tk.Label(left_frame, text="Fonte: Tesouro Nacional", bg='black', fg='white', anchor='w')
        label_fonte.pack(side=tk.LEFT, padx=10, pady=10)

        update_plot()
        
        root.mainloop()
        
    except FileNotFoundError:
        print(f"Erro: o arquivo {file_path} não foi encontrado. Verifique o caminho e tente novamente.")
    except pd.errors.ParserError:
        print("Erro ao ler o arquivo CSV. Verifique o formato do arquivo.")
    except Exception as e:
        print(f"Erro ao processar os dados: {e}")

def get_curve_values(df):
    if df.empty:
        return None, None
    x = ((df['Data Vencimento'] - df['Data Base']).dt.days / 365.25).values
    y = df['Taxa Indicativa'].values
    mask = x >= -0.5  # Incluir vencimentos recentes, evitar anos negativos
    return x[mask], y[mask]

def plot_curve(ax, df, date_label, label):
    x, y = get_curve_values(df)
    if x is None or y is None:
        return x, y, (x, y, label)

    x_new = np.linspace(x.min(), x.max(), 500)
    cs = CubicSpline(x, y)
    y_new = cs(x_new)
    
    ax.plot(x, y, 'o', markersize=5)
    ax.plot(x_new, y_new, linestyle='--', label=f'{label} Interpolada - {date_label}')
    ax.set_xlabel('Anos até o Vencimento')
    ax.set_ylabel('Taxa Indicativa (%)' if label == 'IPCA+' else 'Taxa Prefixada (%)')
    ax.set_xticks(np.arange(0, x.max() + 1, 1))
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    ax.spines['bottom'].set_color('white')
    ax.spines['top'].set_color('white') 
    ax.spines['right'].set_color('white')
    ax.spines['left'].set_color('white')

    return x, y, (x, y, label)

def calculate_inflation_implicit(df_prefixada, df_ipca):
    x_prefixada, y_prefixada = get_curve_values(df_prefixada)
    x_ipca, y_ipca = get_curve_values(df_ipca)
    
    if x_ipca is not None and x_prefixada is not None:
        x_common = np.linspace(min(x_prefixada.min(), x_ipca.min()), min(10, max(x_prefixada.max(), x_ipca.max())), 500)
        cs_prefixada = CubicSpline(x_prefixada, y_prefixada)
        cs_ipca = CubicSpline(x_ipca, y_ipca)
        
        y_prefixada_interp = cs_prefixada(x_common)
        y_ipca_interp = cs_ipca(x_common)
        y_inflacao_implicita = y_prefixada_interp - y_ipca_interp
        
        df_inflacao_implicita = pd.DataFrame({'x': x_common, 'y': y_inflacao_implicita})
        return df_inflacao_implicita
    return pd.DataFrame()

def main():
    download_csv(url, local_path)
    process_data(local_path)

if __name__ == "__main__":
    main()