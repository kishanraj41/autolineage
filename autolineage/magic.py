"""
Jupyter notebook magic commands for AutoLineage.

Usage in Jupyter:
    %load_ext autolineage
    %lineage_start
    
    # Your code here...
    
    %lineage_show
    %lineage_report
"""

from IPython.core.magic import Magics, line_magic, cell_magic, magics_class
from IPython.display import display, HTML, Image
import os


@magics_class
class LineageMagics(Magics):
    """IPython magic commands for lineage tracking."""
    
    def __init__(self, shell):
        super().__init__(shell)
        self.tracker = None
        self.hooks_enabled = False
    
    @line_magic
    def lineage_start(self, line):
        """
        Start lineage tracking in the notebook.
        
        Usage:
            %lineage_start
            %lineage_start --db my_lineage.db
        """
        # Parse arguments
        args = line.split()
        db_path = 'notebook_lineage.db'
        
        for i, arg in enumerate(args):
            if arg == '--db' and i + 1 < len(args):
                db_path = args[i + 1]
        
        # Import here to avoid circular imports
        from .tracker import DatasetTracker
        from .hooks import enable_hooks
        
        if self.tracker is not None:
            print("⚠ Lineage tracking already started")
            return
        
        # Create tracker
        self.tracker = DatasetTracker(db_path)
        self.tracker.start_run('jupyter_notebook')
        
        # Enable hooks
        enable_hooks(self.tracker)
        self.hooks_enabled = True
        
        print(f"✅ Lineage tracking started (database: {db_path})")
        print("   Use %lineage_show to visualize")
        print("   Use %lineage_summary to see stats")
        print("   Use %lineage_stop to end tracking")
    
    @line_magic
    def lineage_stop(self, line):
        """
        Stop lineage tracking.
        
        Usage:
            %lineage_stop
        """
        if self.tracker is None:
            print("⚠ No active tracking session")
            return
        
        self.tracker.end_run()
        self.tracker.close()
        self.tracker = None
        
        print("✅ Lineage tracking stopped")
    
    @line_magic
    def lineage_summary(self, line):
        """
        Show lineage summary.
        
        Usage:
            %lineage_summary
        """
        if self.tracker is None:
            print("⚠ Tracking not started. Use %lineage_start first")
            return
        
        summary = self.tracker.get_lineage_summary()
        
        print("="*60)
        print("LINEAGE SUMMARY")
        print("="*60)
        print(f"Datasets tracked: {summary['datasets_count']}")
        print(f"Operations: {summary['operations_count']}")
        print(f"Lineage edges: {summary['lineage_edges_count']}")
        
        if summary['graph']:
            print("\nData Flow:")
            for edge in summary['graph']:
                from pathlib import Path
                source = Path(edge['source']).name
                target = Path(edge['target']).name
                op = edge['operation'] or 'transform'
                print(f"  {source} → {target} ({op})")
    
    @line_magic
    def lineage_show(self, line):
        """
        Display lineage graph in the notebook.
        
        Usage:
            %lineage_show
            %lineage_show --format html
            %lineage_show --format png
        """
        if self.tracker is None:
            print("⚠ Tracking not started. Use %lineage_start first")
            return
        
        # Parse format
        format_type = 'html'
        args = line.split()
        for i, arg in enumerate(args):
            if arg == '--format' and i + 1 < len(args):
                format_type = args[i + 1]
        
        from .graph import LineageGraph
        
        # Create graph
        graph = LineageGraph(self.tracker.db)
        graph.build()
        
        if graph.graph.number_of_nodes() == 0:
            print("⚠ No lineage data to visualize yet")
            return
        
        if format_type == 'html':
            # Generate interactive HTML
            output_path = 'notebook_lineage.html'
            graph.visualize_plotly(output_path)
            
            # Read and display
            with open(output_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            display(HTML(html_content))
            
        elif format_type == 'png':
            # Generate PNG
            output_path = 'notebook_lineage.png'
            graph.visualize_matplotlib(output_path)
            
            # Display image
            display(Image(filename=output_path))
        
        else:
            print(f"⚠ Unknown format: {format_type}")
            print("   Supported formats: html, png")
    
    @line_magic
    def lineage_report(self, line):
        """
        Generate and display compliance report.
        
        Usage:
            %lineage_report
            %lineage_report --save compliance.md
        """
        if self.tracker is None:
            print("⚠ Tracking not started. Use %lineage_start first")
            return
        
        from .reporter import ComplianceReporter
        
        # Parse arguments
        save_path = None
        args = line.split()
        for i, arg in enumerate(args):
            if arg == '--save' and i + 1 < len(args):
                save_path = args[i + 1]
        
        # Generate report
        reporter = ComplianceReporter(self.tracker.db)
        report_md = reporter.generate_markdown()
        
        # Save if requested
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(report_md)
            print(f"✅ Report saved to {save_path}")
        
        # Display in notebook
        display(HTML(f"<pre>{report_md}</pre>"))
    
    @cell_magic
    def lineage_track(self, line, cell):
        """
        Track lineage for a specific cell.
        
        Usage:
            %%lineage_track
            df = pd.read_csv('data.csv')
            df.to_csv('output.csv')
        """
        # Auto-start if not started
        if self.tracker is None:
            print("Auto-starting lineage tracking...")
            self.lineage_start('')
        
        # Execute the cell
        self.shell.run_cell(cell)
        
        # Show quick summary
        if self.tracker:
            summary = self.tracker.get_lineage_summary()
            print(f"\n✓ Cell tracked: {summary['datasets_count']} datasets, {summary['lineage_edges_count']} edges")


# IPython extension load/unload functions
def load_ipython_extension(ipython):
    """
    Load the extension in IPython.
    
    Called automatically when: %load_ext autolineage
    """
    ipython.register_magics(LineageMagics)
    
    print("="*60)
    print("AutoLineage Jupyter Extension Loaded! 🚀")
    print("="*60)
    print("\nAvailable magic commands:")
    print("  %lineage_start         - Start tracking")
    print("  %lineage_stop          - Stop tracking")
    print("  %lineage_summary       - Show summary")
    print("  %lineage_show          - Display graph")
    print("  %lineage_report        - Generate compliance report")
    print("  %%lineage_track        - Track a cell")
    print("\nGet started:")
    print("  %lineage_start")
    print("="*60)


def unload_ipython_extension(ipython):
    """
    Unload the extension.
    
    Called when: %unload_ext autolineage
    """
    print("AutoLineage extension unloaded")