"""
Command-line interface for AutoLineage.
"""

import click
import sys
import os
from pathlib import Path


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """
    AutoLineage - Automatic ML Data Lineage Tracking
    
    Track your data lineage automatically from raw data to trained models.
    """
    pass


@cli.command()
@click.argument('script_path', type=click.Path(exists=True))
@click.option('--db', default='lineage.db', help='Database path')
def track(script_path, db):
    """
    Track lineage for a Python script.
    
    Example:
        lineage track my_pipeline.py
    """
    click.echo(f"\n{'='*60}")
    click.echo(f"AutoLineage: Tracking {script_path}")
    click.echo(f"{'='*60}\n")
    
    # Clean up old db if fresh start requested
    # (for now, we append to existing db)
    
    # Import tracking
    from .tracker import DatasetTracker
    from .hooks import enable_hooks
    
    # Create tracker
    tracker = DatasetTracker(db)
    tracker.start_run(script_path)
    
    # Enable hooks
    enable_hooks(tracker)
    
    # Execute script
    try:
        with open(script_path) as f:
            code = f.read()
        
        # Create a clean namespace
        namespace = {
            '__name__': '__main__',
            '__file__': os.path.abspath(script_path),
        }
        
        # Execute
        exec(code, namespace)
        
        # End tracking
        tracker.end_run('completed')
        
        click.echo(f"\n{'='*60}")
        click.echo("✅ Tracking completed successfully")
        click.echo(f"{'='*60}\n")
        
        # Show summary
        summary = tracker.get_lineage_summary()
        click.echo(f"Tracked {summary['datasets_count']} datasets")
        click.echo(f"Recorded {summary['operations_count']} operations")
        click.echo(f"Created {summary['lineage_edges_count']} lineage edges")
        
        click.echo(f"\nDatabase: {db}")
        click.echo(f"View graph: lineage show --db {db}")
        
    except Exception as e:
        tracker.end_run('failed')
        click.echo(f"\n❌ Error: {e}", err=True)
        sys.exit(1)
    
    finally:
        tracker.close()


@cli.command()
@click.option('--db', default='lineage.db', help='Database path')
@click.option('--output', '-o', default='lineage_graph.png', help='Output file')
@click.option('--format', type=click.Choice(['png', 'html']), default='png', help='Output format')
def show(db, output, format):
    """
    Visualize the lineage graph.
    
    Example:
        lineage show --output graph.png
        lineage show --format html --output graph.html
    """
    if not os.path.exists(db):
        click.echo(f"❌ Database not found: {db}", err=True)
        sys.exit(1)
    
    from .database import LineageDatabase
    from .graph import LineageGraph
    
    # Load database
    database = LineageDatabase(db)
    
    # Create graph
    graph = LineageGraph(database)
    graph.build()
    
    # Check if empty
    if graph.graph.number_of_nodes() == 0:
        click.echo("⚠ No lineage data found in database")
        database.close()
        sys.exit(0)
    
    # Generate visualization
    click.echo(f"\nGenerating {format.upper()} visualization...")
    
    if format == 'png':
        graph.visualize_matplotlib(output)
    else:
        graph.visualize_plotly(output)
    
    click.echo(f"✓ Saved to {output}")
    
    # Show stats
    stats = graph.get_stats()
    click.echo(f"\nGraph Statistics:")
    click.echo(f"  Nodes: {stats['nodes']}")
    click.echo(f"  Edges: {stats['edges']}")
    click.echo(f"  Sources: {len(stats['sources'])}")
    click.echo(f"  Sinks: {len(stats['sinks'])}")
    
    database.close()


@cli.command()
@click.option('--db', default='lineage.db', help='Database path')
def summary(db):
    """
    Show lineage summary.
    
    Example:
        lineage summary
    """
    if not os.path.exists(db):
        click.echo(f"❌ Database not found: {db}", err=True)
        sys.exit(1)
    
    from .database import LineageDatabase
    
    database = LineageDatabase(db)
    
    # Get all data
    datasets = database.get_all_datasets()
    operations = database.get_all_operations()
    graph_data = database.get_lineage_graph()
    
    click.echo(f"\n{'='*60}")
    click.echo("LINEAGE SUMMARY")
    click.echo(f"{'='*60}\n")
    
    click.echo(f"Datasets: {len(datasets)}")
    click.echo(f"Operations: {len(operations)}")
    click.echo(f"Lineage edges: {len(graph_data)}")
    
    if datasets:
        click.echo(f"\n{'='*60}")
        click.echo("DATASETS")
        click.echo(f"{'='*60}")
        
        for ds in datasets[:10]:  # Show first 10
            filename = Path(ds['filepath']).name
            click.echo(f"\n• {filename}")
            click.echo(f"  Hash: {ds['hash'][:16]}...")
            click.echo(f"  Size: {ds['size']} bytes")
            click.echo(f"  Format: {ds['format']}")
        
        if len(datasets) > 10:
            click.echo(f"\n... and {len(datasets) - 10} more")
    
    if graph_data:
        click.echo(f"\n{'='*60}")
        click.echo("DATA FLOW")
        click.echo(f"{'='*60}")
        
        for edge in graph_data[:10]:  # Show first 10
            source = Path(edge['source']).name
            target = Path(edge['target']).name
            op = edge['operation'] or 'unknown'
            click.echo(f"  {source} → {target} ({op})")
        
        if len(graph_data) > 10:
            click.echo(f"\n... and {len(graph_data) - 10} more edges")
    
    database.close()

@cli.command()
@click.option('--db', default='lineage.db', help='Database path')
@click.option('--format', type=click.Choice(['markdown', 'json', 'both']), default='markdown', help='Report format')
@click.option('--output', '-o', default=None, help='Output file path')
def report(db, format, output):
    """
    Generate EU AI Act compliance report.
    
    Example:
        lineage report --format markdown
        lineage report --format json --output compliance.json
        lineage report --format both
    """
    if not os.path.exists(db):
        click.echo(f"❌ Database not found: {db}", err=True)
        sys.exit(1)
    
    from .database import LineageDatabase
    from .reporter import ComplianceReporter
    
    database = LineageDatabase(db)
    reporter = ComplianceReporter(database)
    
    click.echo(f"\n{'='*60}")
    click.echo("GENERATING COMPLIANCE REPORT")
    click.echo(f"{'='*60}\n")
    
    if format in ['markdown', 'both']:
        md_path = output or 'compliance_report.md'
        reporter.save_markdown(md_path)
        click.echo(f"✓ Markdown report: {md_path}")
    
    if format in ['json', 'both']:
        json_path = output or 'compliance_report.json'
        if format == 'both' and not output:
            json_path = 'compliance_report.json'
        reporter.save_json(json_path)
        click.echo(f"✓ JSON report: {json_path}")
    
    click.echo(f"\n{'='*60}")
    click.echo("✅ Compliance report generated")
    click.echo(f"{'='*60}\n")
    
    database.close()
@cli.command()
@click.option('--db', default='lineage.db', help='Database path')
def clear(db):
    """
    Clear/delete the lineage database.
    
    Example:
        lineage clear
    """
    if not os.path.exists(db):
        click.echo(f"⚠ Database not found: {db}")
        sys.exit(0)
    
    if click.confirm(f"Are you sure you want to delete {db}?"):
        os.remove(db)
        click.echo(f"✓ Deleted {db}")
    else:
        click.echo("Cancelled")


if __name__ == '__main__':
    cli()