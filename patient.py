from fastapi import FastAPI,Query,HTTPException,Path
import requests,json

app=FastAPI()

def load_data():
    with open("patients.json","r") as f:
        data=json.load(f)
    return data 
@app.get("/")
def read_main():
    return {"message": "Hello World from main app"}
@app.get("/patient")
def read_main():
    data=load_data()
    return data
@app.get("/patient/{patient_id}")
def read_patient(patient_id:str=Path(...,description="Please enter id in this form: "
                                     ,example="P001")):
    data=load_data()
    if patient_id in data:
        return data[patient_id]
    else:
        raise HTTPException(status_code=404,detail="Patient not found")
# @app.get("/sorted")
# def sorted_patient(sort_by:str=Query(...,description="Sort the data on the basics of weight,hight or bmi"),
#                    order:str=Query('asc',description="Sort on the basics of ascending or descending orer.")):
#     valid_fields=['weight','hight','bmi']
#     if sort_by not in valid_fields:
#         raise HTTPException(status_code=400,detail=f"Invalid field select from {valid_fields}")
#     # if order not in valid_fields:
#     #     raise HTTPException(status_code=400,detail=f"Invalid order select from [asc , dec]")
#     if order not in valid_fields: # This checks order against ['weight','hight','bmi']
#         raise HTTPException(status_code=400,detail=f"Invalid order select from [asc , dec]")

#     data=load_data()
#     sort_order = True if order == 'desc' else False
#     sorted_data=sorted(data.values(),key=lambda x: x.get(sort_by,0),reverse=sort_order)
@app.get("/sorted")
def sorted_patient(
    sort_by: str = Query(..., description="Sort the data on the basis of weight, height, or bmi"),
    order: str = Query('asc', description="Sort on the basis of ascending or descending order.")
):
    # Fix 'hight' typo to 'height' for better practice
    valid_fields = ['weight', 'height', 'bmi'] 
    valid_orders = ['asc', 'desc'] # Define a proper list for orders

    if sort_by not in valid_fields:
        raise HTTPException(status_code=400, detail=f"Invalid field. Select from {valid_fields}")
    
    # *** FIX IS HERE ***
    if order not in valid_orders:
        # Check against the correct list (valid_orders)
        raise HTTPException(status_code=400, detail=f"Invalid order. Select from {valid_orders}")

    data = load_data()
    
    # Determine the reverse flag
    sort_order_reverse = (order == 'desc')
    
    # Sort the data
    sorted_data = sorted(
        data.values(), 
        key=lambda x: x.get(sort_by, 0), 
        reverse=sort_order_reverse
    )
    
    # *** CRITICAL FIX: Return the result ***
    return sorted_data
