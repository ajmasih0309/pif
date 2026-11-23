```mermaid
erDiagram
    SHOP ||--o{ ORDER : "fulfills at"
    SHOP ||--o{ BIKE : "stores at"
    SHOP ||--o{ PUBLIC_REPAIR_EVENT : "hosts"

    CONTACT ||--o{ ORDER : "places"
    RECIPIENT ||--o{ ORDER : "receives"
    BIKE ||--o{ ORDER : "assigned to (optional)"

    VOLUNTEER ||--o{ BIKE : "finished by (optional)"

    SHOP {
      int ShopID PK
      string ShopName "Rogers/Bentonville"
    }

    CONTACT {
      int ContactID PK
      string ContactName
      string PhoneNumber
      string ContactEmail
    }

    RECIPIENT {
      int RecipientID PK
      string RecipientName
      string Gender "M/F/Other/Unknown"
      int Age
      decimal HeightValue
      string HeightUnit "in/cm"
    }

    ORDER {
      int OrderID PK
      string OrderNumber UK
      string OrderType "Standard/Specialty"
      boolean PickUpFlag
      string PedalPartner
      date OrderDate
      date DatePickedUp
      string BikeTypeFirstChoice
      string BikeTypeSecondChoice
      string Notes
      int ShopID FK
      int ContactID FK
      int RecipientID FK
      int BikeID FK "nullable"
    }

    BIKE {
      int BikeID PK
      datetime FinishedTimestamp
      string BikeTagNumber UK
      string Make
      string Model
      string Color
      string WheelSize
      string BikeType
      int ShopID FK
      int VolunteerID FK "nullable"
    }

    VOLUNTEER {
      int VolunteerID PK
      string VolunteerName
    }

    PUBLIC_REPAIR_EVENT {
      int RepairEventID PK
      datetime EventTimestamp
      int NumberOfBikesRepaired
      string ReportedByName
      int ShopID FK
    }