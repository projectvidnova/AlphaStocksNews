#!/bin/bash

# Monitor AlphaStock Workflow Progress

echo "📊 AlphaStock Workflow Monitor"
echo "==============================="
echo ""

# Check if workflow is running
if pgrep -f "complete_workflow.py" > /dev/null; then
    echo "✅ Workflow is RUNNING"
    echo ""
    
    # Show recent progress
    echo "📈 Recent Activity (last 20 lines):"
    echo "-----------------------------------"
    tail -20 workflow_output.log | grep -E "INFO:kite_api_client:Fetched|Phase|✅|❌|SUCCESS|FAILED" || tail -20 workflow_output.log
    echo ""
    
    # Count data fetched
    records_fetched=$(grep -c "Fetched.*historical records" workflow_output.log 2>/dev/null || echo "0")
    echo "📦 API Calls Made: $records_fetched"
    echo ""
    
    # Estimate completion
    echo "⏱️  Estimated time: 10-15 minutes total"
    echo "   (Downloading 3 years of Bank Nifty data)"
    echo ""
    
    echo "🔄 To watch live: tail -f workflow_output.log"
    echo "🛑 To stop: pkill -f complete_workflow.py"
    
else
    echo "⚠️  Workflow is NOT running"
    echo ""
    
    # Check if it completed
    if [ -f "workflow_output.log" ]; then
        echo "📋 Last Status:"
        echo "-----------------------------------"
        tail -30 workflow_output.log | grep -E "Phase|✅|❌|SUCCESS|FAILED|COMPLETE" || echo "Check workflow_output.log for details"
        echo ""
        
        # Check for success
        if grep -q "WORKFLOW COMPLETE" workflow_output.log; then
            echo "🎉 Workflow completed successfully!"
        elif grep -q "ERROR" workflow_output.log | tail -1; then
            echo "❌ Workflow ended with errors"
        fi
    else
        echo "No workflow output found"
    fi
fi

echo ""
