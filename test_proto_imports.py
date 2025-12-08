"""
Test rapid pentru a verifica că toate clasele ProtoOA sunt disponibile
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ctrader_official'))

from loguru import logger

logger.info("🧪 Testing ProtoOA imports...")

try:
    from ctrader_open_api.messages import OpenApiMessages_pb2 as msg
    from ctrader_open_api.messages import OpenApiModelMessages_pb2 as model
    from ctrader_open_api.messages import OpenApiCommonMessages_pb2 as common
    
    logger.success("✅ All message modules imported!")
    
    # Test specific classes
    classes_to_test = [
        'ProtoOAApplicationAuthReq',
        'ProtoOAApplicationAuthRes',
        'ProtoOAAccountAuthReq',
        'ProtoOAAccountAuthRes',
        'ProtoOASymbolsListReq',
        'ProtoOASymbolsListRes',
        'ProtoOAGetTrendbarReq',
        'ProtoOAGetTrendbarRes',
        'ProtoOANewOrderReq',
        'ProtoOAExecutionEvent',
        'ProtoOATraderReq',
        'ProtoOATraderRes',
        'ProtoOADealListReq',
        'ProtoOADealListRes',
    ]
    
    for cls_name in classes_to_test:
        if hasattr(msg, cls_name):
            logger.success(f"✅ {cls_name}")
        else:
            logger.error(f"❌ {cls_name} NOT FOUND")
    
    # Test enums
    logger.info("\n📋 Testing enums...")
    
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
        ProtoOATrendbarPeriod,
        ProtoOAOrderType,
        ProtoOATradeSide,
        ProtoOAExecutionType
    )
    
    logger.success(f"✅ ProtoOATrendbarPeriod.D1 = {ProtoOATrendbarPeriod.D1}")
    logger.success(f"✅ ProtoOAOrderType.MARKET = {ProtoOAOrderType.MARKET}")
    logger.success(f"✅ ProtoOATradeSide.BUY = {ProtoOATradeSide.BUY}")
    
    logger.success("\n🎉 ALL IMPORTS SUCCESSFUL!")
    logger.info("ProtoOA library is ready to use!")
    
except Exception as e:
    logger.error(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
