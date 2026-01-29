"""
Graph generation and visualization for lineage data.
"""

import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional, Dict, List
import os


class LineageGraph:
    """Generate and visualize lineage graphs."""
    
    def __init__(self, db):
        """
        Initialize graph generator.
        
        Args:
            db: LineageDatabase instance
        """
        self.db = db
        self.graph = nx.DiGraph()
        self._built = False
    
    def build(self, run_id: Optional[str] = None):
        """
        Build lineage graph from database.
        
        Args:
            run_id: Optional run ID to filter by
        """
        self.graph.clear()
        
        # Get lineage data
        edges = self.db.get_lineage_graph()
        
        if not edges:
            print("⚠ No lineage data found")
            return
        
        # Add nodes and edges
        for edge in edges:
            source = Path(edge['source']).name  # Just filename
            target = Path(edge['target']).name
            operation = edge['operation'] or 'unknown'
            op_type = edge['operation_type']
            
            # Add edge with metadata
            self.graph.add_edge(
                source, 
                target,
                operation=operation,
                type=op_type,
                timestamp=edge['created_at']
            )
        
        self._built = True
        print(f"✓ Graph built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
    
    def get_node_color(self, node: str) -> str:
        """
        Get color for a node based on file type.
        
        Args:
            node: Node name (filename)
            
        Returns:
            Color string
        """
        ext = Path(node).suffix.lower()
        
        color_map = {
            '.csv': '#4CAF50',      # Green
            '.parquet': '#2196F3',  # Blue
            '.json': '#FF9800',     # Orange
            '.pkl': '#9C27B0',      # Purple
            '.pickle': '#9C27B0',
            '.npy': '#F44336',      # Red
            '.txt': '#795548',      # Brown
            '.xlsx': '#00BCD4',     # Cyan
            '.xls': '#00BCD4',
        }
        
        return color_map.get(ext, '#9E9E9E')  # Gray default
    
    def visualize_matplotlib(
        self, 
        output_path: str = 'lineage_graph.png',
        figsize: tuple = (12, 8),
        dpi: int = 300
    ):
        """
        Create visualization using matplotlib.
        
        Args:
            output_path: Path to save the image
            figsize: Figure size (width, height)
            dpi: Image resolution
        """
        if not self._built:
            self.build()
        
        if self.graph.number_of_nodes() == 0:
            print("⚠ Empty graph, nothing to visualize")
            return
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        
        # Layout
        try:
            # Try hierarchical layout (works well for DAGs)
            pos = nx.spring_layout(self.graph, k=2, iterations=50)
        except:
            # Fallback to spring layout
            pos = nx.spring_layout(self.graph)
        
        # Node colors based on file type
        node_colors = [self.get_node_color(node) for node in self.graph.nodes()]
        
        # Draw nodes
        nx.draw_networkx_nodes(
            self.graph, pos,
            node_color=node_colors,
            node_size=3000,
            alpha=0.9,
            ax=ax
        )
        
        # Draw edges
        nx.draw_networkx_edges(
            self.graph, pos,
            edge_color='#666666',
            arrows=True,
            arrowsize=20,
            arrowstyle='->',
            width=2,
            alpha=0.6,
            ax=ax
        )
        
        # Draw labels
        nx.draw_networkx_labels(
            self.graph, pos,
            font_size=10,
            font_weight='bold',
            font_color='white',
            ax=ax
        )
        
        # Draw edge labels (operations)
        edge_labels = nx.get_edge_attributes(self.graph, 'operation')
        nx.draw_networkx_edge_labels(
            self.graph, pos,
            edge_labels=edge_labels,
            font_size=8,
            font_color='#333333',
            ax=ax
        )
        
        # Title
        ax.set_title(
            'Data Lineage Graph',
            fontsize=16,
            fontweight='bold',
            pad=20
        )
        
        # Remove axis
        ax.axis('off')
        
        # Tight layout
        plt.tight_layout()
        
        # Save
        plt.savefig(output_path, bbox_inches='tight', dpi=dpi)
        plt.close()
        
        print(f"✓ Graph saved to {output_path}")
        return output_path
    
    def visualize_plotly(self, output_path: str = 'lineage_graph.html'):
        """
        Create interactive visualization using Plotly.
        
        Args:
            output_path: Path to save HTML file
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            print("⚠ Plotly not installed. Install with: pip install plotly")
            return None
        
        if not self._built:
            self.build()
        
        if self.graph.number_of_nodes() == 0:
            print("⚠ Empty graph, nothing to visualize")
            return
        
        # Layout
        pos = nx.spring_layout(self.graph, k=2, iterations=50)
        
        # Create edges
        edge_x = []
        edge_y = []
        for edge in self.graph.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.append(x0)
            edge_x.append(x1)
            edge_x.append(None)
            edge_y.append(y0)
            edge_y.append(y1)
            edge_y.append(None)
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=2, color='#888'),
            hoverinfo='none',
            mode='lines'
        )
        
        # Create nodes
        node_x = []
        node_y = []
        node_text = []
        node_colors = []
        
        for node in self.graph.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Node info
            in_edges = list(self.graph.in_edges(node))
            out_edges = list(self.graph.out_edges(node))
            
            text = f"{node}<br>"
            text += f"Inputs: {len(in_edges)}<br>"
            text += f"Outputs: {len(out_edges)}"
            node_text.append(text)
            
            node_colors.append(self.get_node_color(node))
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=[Path(n).name for n in self.graph.nodes()],
            textposition="top center",
            hovertext=node_text,
            marker=dict(
                color=node_colors,
                size=30,
                line=dict(width=2, color='white')
            )
        )
        
        # Create figure
        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title=dict(
                    text='Data Lineage Graph (Interactive)',
                    font=dict(size=16)
                ),
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor='white'
            )
        )
        
        # Save
        fig.write_html(output_path)
        print(f"✓ Interactive graph saved to {output_path}")
        
        return output_path
    
    def to_text(self) -> str:
        """
        Generate text representation of the graph.
        
        Returns:
            Text description of lineage
        """
        if not self._built:
            self.build()
        
        if self.graph.number_of_nodes() == 0:
            return "Empty graph"
        
        lines = []
        lines.append("Data Lineage Graph")
        lines.append("=" * 60)
        lines.append(f"Nodes: {self.graph.number_of_nodes()}")
        lines.append(f"Edges: {self.graph.number_of_edges()}")
        lines.append("")
        
        # List all edges
        lines.append("Data Flow:")
        lines.append("-" * 60)
        
        for source, target, data in self.graph.edges(data=True):
            operation = data.get('operation', 'unknown')
            lines.append(f"  {source} → {target}")
            lines.append(f"    Operation: {operation}")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_stats(self) -> Dict:
        """
        Get graph statistics.
        
        Returns:
            Dictionary with graph metrics
        """
        if not self._built:
            self.build()
        
        return {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'is_dag': nx.is_directed_acyclic_graph(self.graph),
            'sources': [n for n in self.graph.nodes() if self.graph.in_degree(n) == 0],
            'sinks': [n for n in self.graph.nodes() if self.graph.out_degree(n) == 0],
        }