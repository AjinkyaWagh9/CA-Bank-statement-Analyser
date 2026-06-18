from openpyxl.chart import BarChart, LineChart, PieChart, Reference

def create_line_chart(title: str, ws, min_col: int, min_row: int, max_col: int, max_row: int, 
                      cats_col: int, cats_row_start: int, cats_row_end: int):
    """Creates a Line chart and returns it."""
    chart = LineChart()
    chart.title = title
    chart.style = 13
    
    data = Reference(ws, min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row)
    cats = Reference(ws, min_col=cats_col, min_row=cats_row_start, max_row=cats_row_end)
    
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    
    chart.width = 16
    chart.height = 10
    return chart

def create_stacked_bar_chart(title: str, ws, min_col: int, min_row: int, max_col: int, max_row: int, 
                             cats_col: int, cats_row_start: int, cats_row_end: int):
    """Creates a Stacked Column chart and returns it."""
    chart = BarChart()
    chart.type = "col"
    chart.style = 10
    chart.grouping = "stacked"
    chart.overlap = 100
    chart.title = title
    
    data = Reference(ws, min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row)
    cats = Reference(ws, min_col=cats_col, min_row=cats_row_start, max_row=cats_row_end)
    
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    
    chart.width = 16
    chart.height = 10
    return chart

def create_combo_chart(title: str, ws, min_col: int, min_row: int, max_col: int, max_row: int, 
                       cats_col: int, cats_row_start: int, cats_row_end: int):
    """Creates a Combo chart (Column + Line) and returns it."""
    # Column chart
    chart_bar = BarChart()
    chart_bar.type = "col"
    chart_bar.style = 10
    chart_bar.title = title
    
    data = Reference(ws, min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row)
    cats = Reference(ws, min_col=cats_col, min_row=cats_row_start, max_row=cats_row_end)
    
    chart_bar.add_data(data, titles_from_data=True)
    chart_bar.set_categories(cats)
    
    # Line chart representing the same closing balance series
    chart_line = LineChart()
    chart_line.add_data(data, titles_from_data=True)
    chart_line.set_categories(cats)
    
    # Combine line chart onto column chart
    chart_bar += chart_line
    
    chart_bar.width = 16
    chart_bar.height = 10
    return chart_bar

def create_pie_chart(title: str, ws, min_col: int, min_row: int, max_col: int, max_row: int, 
                      cats_col: int, cats_row_start: int, cats_row_end: int):
    """Creates a Pie chart and returns it."""
    chart = PieChart()
    chart.title = title
    
    data = Reference(ws, min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row)
    cats = Reference(ws, min_col=cats_col, min_row=cats_row_start, max_row=cats_row_end)
    
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    
    chart.width = 12
    chart.height = 8
    return chart

def create_donut_chart(title: str, ws, min_col: int, min_row: int, max_col: int, max_row: int, 
                       cats_col: int, cats_row_start: int, cats_row_end: int):
    """Creates a Donut chart (PieChart with holeSize) and returns it."""
    chart = PieChart()
    chart.title = title
    chart.holeSize = 50
    
    data = Reference(ws, min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row)
    cats = Reference(ws, min_col=cats_col, min_row=cats_row_start, max_row=cats_row_end)
    
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    
    chart.width = 12
    chart.height = 8
    return chart
